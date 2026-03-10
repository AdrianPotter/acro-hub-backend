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


def _log_response(response: dict) -> dict:
    """Log the HTTP status code of an outgoing response and return it unchanged."""
    logger.info("Returning status %d", response["statusCode"])
    return response


# ── Handlers ─────────────────────────────────────────────────────────────────

def login(event, context):
    """POST /auth/login — authenticate with email + password."""
    logger.info("login called")
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        logger.warning("login: invalid JSON body")
        return _log_response(_bad_request("Invalid JSON body"))

    email = body.get("email")
    password = body.get("password")
    logger.info("login: email=%s", email)
    if not email or not password:
        logger.warning("login: missing required field(s) — email=%s, password_provided=%s", email, bool(password))
        return _log_response(_bad_request("email and password are required"))

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
            logger.warning("login: authentication failed for email=%s — %s", email, code)
            return _log_response(_error(401, "Invalid credentials"))
        if code == "UserNotConfirmedException":
            logger.warning("login: user not confirmed for email=%s", email)
            return _log_response(_error(403, "User not confirmed. Please verify your email."))
        logger.error("login: unexpected Cognito error for email=%s — %s", email, exc)
        return _log_response(_error(500, "Authentication error"))

    logger.info("login: successful for email=%s", email)
    auth_result = response.get("AuthenticationResult", {})
    return _log_response(
        _ok(
            {
                "accessToken": auth_result.get("AccessToken"),
                "idToken": auth_result.get("IdToken"),
                "refreshToken": auth_result.get("RefreshToken"),
                "expiresIn": auth_result.get("ExpiresIn"),
                "tokenType": auth_result.get("TokenType"),
            }
        )
    )


def logout(event, context):
    """POST /auth/logout — globally revoke all tokens for the current user."""
    logger.info("logout called")
    auth_header = (event.get("headers") or {}).get("Authorization") or (
        event.get("headers") or {}
    ).get("authorization", "")

    access_token = auth_header.replace("Bearer ", "").strip()
    if not access_token:
        logger.warning("logout: missing Authorization header / Bearer token")
        return _log_response(_bad_request("Authorization header with Bearer token is required"))

    client = _get_client()
    try:
        client.global_sign_out(AccessToken=access_token)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "NotAuthorizedException":
            logger.warning("logout: token is invalid or already expired — %s", code)
            return _log_response(_error(401, "Token is invalid or already expired"))
        logger.error("logout: unexpected Cognito error — %s", exc)
        return _log_response(_error(500, "Logout error"))

    logger.info("logout: successful")
    return _log_response(_ok({"message": "Logged out successfully"}))


def register(event, context):
    """POST /auth/register — sign up a new user."""
    logger.info("register called")
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        logger.warning("register: invalid JSON body")
        return _log_response(_bad_request("Invalid JSON body"))

    email = body.get("email")
    password = body.get("password")
    name = body.get("name", "")
    logger.info("register: email=%s, name=%s", email, name or "<not provided>")
    if not email or not password:
        logger.warning("register: missing required field(s) — email=%s, password_provided=%s", email, bool(password))
        return _log_response(_bad_request("email and password are required"))

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
            logger.warning("register: duplicate email=%s — account already exists", email)
            return _log_response(_error(409, "An account with this email already exists"))
        if code == "InvalidPasswordException":
            logger.warning("register: invalid password for email=%s — %s", email, exc.response["Error"]["Message"])
            return _log_response(_bad_request(exc.response["Error"]["Message"]))
        if code == "InvalidParameterException":
            logger.warning("register: invalid parameter for email=%s — %s", email, exc.response["Error"]["Message"])
            return _log_response(_bad_request(exc.response["Error"]["Message"]))
        logger.error("register: unexpected Cognito error for email=%s — %s", email, exc)
        return _log_response(_error(500, "Registration error"))

    logger.info("register: successful for email=%s, userSub=%s", email, response.get("UserSub"))
    return _log_response(
        {
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
    )


def confirm_registration(event, context):
    """POST /auth/confirm-registration — confirm a newly registered user with a verification code."""
    logger.info("confirm_registration called")
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        logger.warning("confirm_registration: invalid JSON body")
        return _log_response(_bad_request("Invalid JSON body"))

    email = body.get("email")
    code = body.get("code")
    logger.info("confirm_registration: email=%s", email)
    if not email or not code:
        logger.warning(
            "confirm_registration: missing required field(s) — email=%s, code_provided=%s",
            email,
            bool(code),
        )
        return _log_response(_bad_request("email and code are required"))

    client = _get_client()
    try:
        client.confirm_sign_up(
            ClientId=COGNITO_CLIENT_ID,
            Username=email,
            ConfirmationCode=code,
        )
    except ClientError as exc:
        err_code = exc.response["Error"]["Code"]
        if err_code == "CodeMismatchException":
            logger.warning("confirm_registration: code mismatch for email=%s", email)
            return _log_response(_error(400, "Invalid verification code"))
        if err_code == "ExpiredCodeException":
            logger.warning("confirm_registration: expired code for email=%s", email)
            return _log_response(_error(400, "Verification code has expired"))
        if err_code == "UserNotFoundException":
            logger.warning("confirm_registration: user not found — email=%s", email)
            return _log_response(_error(404, "User not found"))
        if err_code == "NotAuthorizedException":
            logger.warning("confirm_registration: user already confirmed for email=%s", email)
            return _log_response(_error(409, "User is already confirmed"))
        logger.error("confirm_registration: unexpected Cognito error for email=%s — %s", email, exc)
        return _log_response(_error(500, "Registration confirmation error"))

    logger.info("confirm_registration: successful for email=%s", email)
    return _log_response(_ok({"message": "Registration confirmed successfully"}))


def forgot_password(event, context):
    """POST /auth/forgot-password — initiate the Cognito forgot-password flow."""
    logger.info("forgot_password called")
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        logger.warning("forgot_password: invalid JSON body")
        return _log_response(_bad_request("Invalid JSON body"))

    email = body.get("email")
    logger.info("forgot_password: email=%s", email)
    if not email:
        logger.warning("forgot_password: missing required field — email")
        return _log_response(_bad_request("email is required"))

    client = _get_client()
    try:
        client.forgot_password(ClientId=COGNITO_CLIENT_ID, Username=email)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "UserNotFoundException":
            # Return success to avoid user enumeration; log internally for diagnostics
            logger.info("forgot_password: user not found for email=%s — returning generic success to prevent enumeration", email)
            return _log_response(_ok({"message": "If the account exists, a reset code has been sent"}))
        if code == "InvalidParameterException":
            logger.warning("forgot_password: invalid parameter for email=%s — %s", email, exc.response["Error"]["Message"])
            return _log_response(_bad_request(exc.response["Error"]["Message"]))
        logger.error("forgot_password: unexpected Cognito error for email=%s — %s", email, exc)
        return _log_response(_error(500, "Password reset error"))

    logger.info("forgot_password: reset code sent for email=%s", email)
    return _log_response(_ok({"message": "Password reset code sent to your email"}))


def confirm_password(event, context):
    """POST /auth/confirm-password — confirm a new password with the reset code."""
    logger.info("confirm_password called")
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        logger.warning("confirm_password: invalid JSON body")
        return _log_response(_bad_request("Invalid JSON body"))

    email = body.get("email")
    code = body.get("code")
    new_password = body.get("newPassword")
    logger.info("confirm_password: email=%s", email)
    if not email or not code or not new_password:
        logger.warning(
            "confirm_password: missing required field(s) — email=%s, code_provided=%s, newPassword_provided=%s",
            email, bool(code), bool(new_password),
        )
        return _log_response(_bad_request("email, code and newPassword are required"))

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
            logger.warning("confirm_password: code mismatch for email=%s", email)
            return _log_response(_error(400, "Invalid verification code"))
        if err_code == "ExpiredCodeException":
            logger.warning("confirm_password: expired code for email=%s", email)
            return _log_response(_error(400, "Verification code has expired"))
        if err_code == "UserNotFoundException":
            logger.warning("confirm_password: user not found — email=%s", email)
            return _log_response(_error(404, "User not found"))
        if err_code == "InvalidPasswordException":
            logger.warning("confirm_password: invalid password for email=%s — %s", email, exc.response["Error"]["Message"])
            return _log_response(_bad_request(exc.response["Error"]["Message"]))
        logger.error("confirm_password: unexpected Cognito error for email=%s — %s", email, exc)
        return _log_response(_error(500, "Password confirmation error"))

    logger.info("confirm_password: successful for email=%s", email)
    return _log_response(_ok({"message": "Password reset successfully"}))


# ── Router ───────────────────────────────────────────────────────────────────

def router(event, context):
    """Route incoming requests to the appropriate handler based on path and method."""
    path = event.get("path", "")
    method = event.get("httpMethod", "").upper()

    logger.info("router: path=%s, method=%s", path, method)

    # Route based on path and method
    if path == "/auth/login" and method == "POST":
        return login(event, context)
    elif path == "/auth/register" and method == "POST":
        return register(event, context)
    elif path == "/auth/logout" and method == "POST":
        return logout(event, context)
    elif path == "/auth/forgot-password" and method == "POST":
        return forgot_password(event, context)
    elif path == "/auth/confirm-registration" and method == "POST":
        return confirm_registration(event, context)
    elif path == "/auth/confirm-password" and method == "POST":
        return confirm_password(event, context)
    elif method == "OPTIONS":
        # Handle CORS preflight requests
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": "",
        }
    else:
        logger.warning("router: unrecognized path=%s, method=%s", path, method)
        return _log_response(_error(404, f"Endpoint {method} {path} not found"))
