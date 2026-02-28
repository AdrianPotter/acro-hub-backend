"""
Acro Hub — Authentication Lambda
Handles login, logout, registration and password reset via Amazon Cognito.
"""
import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")

_cognito = None


def _get_client():
    global _cognito
    if _cognito is None:
        _cognito = boto3.client("cognito-idp")
    return _cognito


# ── Helpers ──────────────────────────────────────────────────────────────────

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "OPTIONS,POST,GET",
    "Content-Type": "application/json",
}


def _ok(body: dict) -> dict:
    return {"statusCode": 200, "headers": CORS_HEADERS, "body": json.dumps(body)}


def _bad_request(message: str) -> dict:
    return {
        "statusCode": 400,
        "headers": CORS_HEADERS,
        "body": json.dumps({"error": message}),
    }


def _error(status: int, message: str) -> dict:
    return {
        "statusCode": status,
        "headers": CORS_HEADERS,
        "body": json.dumps({"error": message}),
    }


def _parse_body(event: dict) -> dict:
    raw = event.get("body") or "{}"
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


# ── Handlers ─────────────────────────────────────────────────────────────────

def login(event, context):
    """POST /auth/login — authenticate with email + password."""
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _bad_request("Invalid JSON body")

    email = body.get("email")
    password = body.get("password")
    if not email or not password:
        return _bad_request("email and password are required")

    client = _get_client()
    try:
        response = client.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": password},
            ClientId=COGNITO_CLIENT_ID,
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("UserNotFoundException", "NotAuthorizedException"):
            return _error(401, "Invalid credentials")
        if code == "UserNotConfirmedException":
            return _error(403, "User not confirmed. Please verify your email.")
        logger.error("Cognito error during login: %s", exc)
        return _error(500, "Authentication error")

    auth_result = response.get("AuthenticationResult", {})
    return _ok(
        {
            "accessToken": auth_result.get("AccessToken"),
            "idToken": auth_result.get("IdToken"),
            "refreshToken": auth_result.get("RefreshToken"),
            "expiresIn": auth_result.get("ExpiresIn"),
            "tokenType": auth_result.get("TokenType"),
        }
    )


def logout(event, context):
    """POST /auth/logout — globally revoke all tokens for the current user."""
    auth_header = (event.get("headers") or {}).get("Authorization") or (
        event.get("headers") or {}
    ).get("authorization", "")

    access_token = auth_header.replace("Bearer ", "").strip()
    if not access_token:
        return _bad_request("Authorization header with Bearer token is required")

    client = _get_client()
    try:
        client.global_sign_out(AccessToken=access_token)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "NotAuthorizedException":
            return _error(401, "Token is invalid or already expired")
        logger.error("Cognito error during logout: %s", exc)
        return _error(500, "Logout error")

    return _ok({"message": "Logged out successfully"})


def register(event, context):
    """POST /auth/register — sign up a new user."""
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _bad_request("Invalid JSON body")

    email = body.get("email")
    password = body.get("password")
    name = body.get("name", "")
    if not email or not password:
        return _bad_request("email and password are required")

    client = _get_client()
    user_attributes = [{"Name": "email", "Value": email}]
    if name:
        user_attributes.append({"Name": "name", "Value": name})

    try:
        response = client.sign_up(
            ClientId=COGNITO_CLIENT_ID,
            Username=email,
            Password=password,
            UserAttributes=user_attributes,
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "UsernameExistsException":
            return _error(409, "An account with this email already exists")
        if code == "InvalidPasswordException":
            return _bad_request(exc.response["Error"]["Message"])
        if code == "InvalidParameterException":
            return _bad_request(exc.response["Error"]["Message"])
        logger.error("Cognito error during register: %s", exc)
        return _error(500, "Registration error")

    return {
        "statusCode": 201,
        "headers": CORS_HEADERS,
        "body": json.dumps(
            {
                "message": "Registration successful. Please check your email to verify your account.",
                "userSub": response.get("UserSub"),
                "confirmed": response.get("UserConfirmed", False),
            }
        ),
    }


def forgot_password(event, context):
    """POST /auth/forgot-password — initiate the Cognito forgot-password flow."""
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _bad_request("Invalid JSON body")

    email = body.get("email")
    if not email:
        return _bad_request("email is required")

    client = _get_client()
    try:
        client.forgot_password(ClientId=COGNITO_CLIENT_ID, Username=email)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "UserNotFoundException":
            # Return success to avoid user enumeration
            return _ok({"message": "If the account exists, a reset code has been sent"})
        if code == "InvalidParameterException":
            return _bad_request(exc.response["Error"]["Message"])
        logger.error("Cognito error during forgot_password: %s", exc)
        return _error(500, "Password reset error")

    return _ok({"message": "Password reset code sent to your email"})


def confirm_password(event, context):
    """POST /auth/confirm-password — confirm a new password with the reset code."""
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _bad_request("Invalid JSON body")

    email = body.get("email")
    code = body.get("code")
    new_password = body.get("newPassword")
    if not email or not code or not new_password:
        return _bad_request("email, code and newPassword are required")

    client = _get_client()
    try:
        client.confirm_forgot_password(
            ClientId=COGNITO_CLIENT_ID,
            Username=email,
            ConfirmationCode=code,
            Password=new_password,
        )
    except ClientError as exc:
        err_code = exc.response["Error"]["Code"]
        if err_code == "CodeMismatchException":
            return _error(400, "Invalid verification code")
        if err_code == "ExpiredCodeException":
            return _error(400, "Verification code has expired")
        if err_code == "UserNotFoundException":
            return _error(404, "User not found")
        if err_code == "InvalidPasswordException":
            return _bad_request(exc.response["Error"]["Message"])
        logger.error("Cognito error during confirm_password: %s", exc)
        return _error(500, "Password confirmation error")

    return _ok({"message": "Password reset successfully"})
