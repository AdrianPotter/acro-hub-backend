"""
Acro Hub — Users Lambda
Admin-only user management: list users, view groups, update groups,
disable/enable accounts, and delete users via Amazon Cognito.

All endpoints require a valid Cognito JWT and the caller must belong
to the 'admins' group.
"""
import json
import logging
import os
import re

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

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
    "Access-Control-Allow-Methods": "OPTIONS,GET,PUT,POST,DELETE",
    "Content-Type": "application/json",
}

# Valid group names as defined in Cognito / Terraform
VALID_GROUPS = {"admins", "curators", "contributors"}


def _ok(body: dict) -> dict:
    return {"statusCode": 200, "headers": CORS_HEADERS, "body": json.dumps(body)}


def _no_content() -> dict:
    return {"statusCode": 204, "headers": CORS_HEADERS, "body": ""}


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


def _get_caller_groups(event: dict) -> list:
    """Return the list of Cognito groups the caller belongs to (from JWT claims)."""
    try:
        raw = event["requestContext"]["authorizer"]["claims"].get("cognito:groups", "")
        if not raw:
            return []
        # The claim is a space-separated or JSON-array-like string depending on SDK version
        if raw.startswith("["):
            return json.loads(raw)
        return raw.split()
    except (KeyError, TypeError, json.JSONDecodeError):
        return []


def _require_admin(event: dict):
    """Return None if the caller is an admin; otherwise return a 403 response."""
    groups = _get_caller_groups(event)
    if "admins" not in groups:
        logger.warning("_require_admin: caller is not in admins group — groups=%s", groups)
        return _error(403, "Admin access required")
    return None


def _format_user(user: dict, groups: list | None = None) -> dict:
    """Convert a Cognito user object into a serialisable dict."""
    attrs = {a["Name"]: a["Value"] for a in user.get("Attributes", [])}
    return {
        "username": user.get("Username", ""),
        "email": attrs.get("email", ""),
        "name": attrs.get("name", ""),
        "sub": attrs.get("sub", ""),
        "status": user.get("UserStatus", ""),
        "enabled": user.get("Enabled", True),
        "createdAt": user.get("UserCreateDate", "").isoformat()
        if hasattr(user.get("UserCreateDate", ""), "isoformat")
        else str(user.get("UserCreateDate", "")),
        "lastLogin": attrs.get("custom:last_login", None),
        "groups": groups if groups is not None else [],
    }


def _get_user_groups(username: str) -> list:
    """Fetch the list of group names a user belongs to."""
    client = _get_client()
    try:
        result = client.admin_list_groups_for_user(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=username,
        )
        return [g["GroupName"] for g in result.get("Groups", [])]
    except ClientError as exc:
        logger.warning("_get_user_groups: failed for username=%s — %s", username, exc)
        return []


# ── Handlers ─────────────────────────────────────────────────────────────────

def list_users(event, context):
    """GET /users — list all Cognito users with their groups and metadata."""
    logger.info("list_users called")
    denied = _require_admin(event)
    if denied:
        return _log_response(denied)

    params = event.get("queryStringParameters") or {}
    filter_str = params.get("filter", "")  # e.g. 'email ^= "alice"'

    client = _get_client()
    kwargs = {"UserPoolId": COGNITO_USER_POOL_ID, "Limit": 60}
    if filter_str:
        kwargs["Filter"] = filter_str

    users = []
    try:
        while True:
            result = client.list_users(**kwargs)
            for u in result.get("Users", []):
                groups = _get_user_groups(u["Username"])
                users.append(_format_user(u, groups))
            pagination_token = result.get("PaginationToken")
            if not pagination_token:
                break
            kwargs["PaginationToken"] = pagination_token
    except ClientError as exc:
        logger.error("list_users: Cognito error — %s", exc)
        return _log_response(_error(500, "Failed to list users"))

    logger.info("list_users: returning %d user(s)", len(users))
    return _log_response(_ok({"users": users, "count": len(users)}))


def get_user(username: str, event, context):
    """GET /users/{username} — retrieve a single user's details and groups."""
    logger.info("get_user called: username=%s", username)
    denied = _require_admin(event)
    if denied:
        return _log_response(denied)

    client = _get_client()
    try:
        result = client.admin_get_user(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=username,
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "UserNotFoundException":
            logger.warning("get_user: user not found — username=%s", username)
            return _log_response(_error(404, "User not found"))
        logger.error("get_user: Cognito error for username=%s — %s", username, exc)
        return _log_response(_error(500, "Failed to get user"))

    # admin_get_user returns a slightly different shape — normalise it
    user_dict = {
        "Username": result.get("Username", ""),
        "Attributes": result.get("UserAttributes", []),
        "UserStatus": result.get("UserStatus", ""),
        "Enabled": result.get("Enabled", True),
        "UserCreateDate": result.get("UserCreateDate", ""),
    }
    groups = _get_user_groups(username)
    return _log_response(_ok(_format_user(user_dict, groups)))


def update_user_groups(username: str, event, context):
    """PUT /users/{username}/groups — replace a user's group memberships."""
    logger.info("update_user_groups called: username=%s", username)
    denied = _require_admin(event)
    if denied:
        return _log_response(denied)

    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        logger.warning("update_user_groups: invalid JSON body")
        return _log_response(_bad_request("Invalid JSON body"))

    desired_groups = body.get("groups")
    if desired_groups is None:
        logger.warning("update_user_groups: missing required field — groups")
        return _log_response(_bad_request("groups is required"))
    if not isinstance(desired_groups, list):
        logger.warning("update_user_groups: groups must be an array")
        return _log_response(_bad_request("groups must be an array"))

    invalid = [g for g in desired_groups if g not in VALID_GROUPS]
    if invalid:
        return _log_response(
            _bad_request(
                f"Invalid group(s): {', '.join(invalid)}. "
                f"Valid groups are: {', '.join(sorted(VALID_GROUPS))}"
            )
        )

    client = _get_client()

    # Verify the user exists
    try:
        client.admin_get_user(UserPoolId=COGNITO_USER_POOL_ID, Username=username)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "UserNotFoundException":
            logger.warning("update_user_groups: user not found — username=%s", username)
            return _log_response(_error(404, "User not found"))
        logger.error("update_user_groups: Cognito error for username=%s — %s", username, exc)
        return _log_response(_error(500, "Failed to update user groups"))

    current_groups = set(_get_user_groups(username))
    desired_set = set(desired_groups)

    to_add = desired_set - current_groups
    to_remove = current_groups - desired_set

    try:
        for group in to_add:
            logger.info("update_user_groups: adding username=%s to group=%s", username, group)
            client.admin_add_user_to_group(
                UserPoolId=COGNITO_USER_POOL_ID,
                Username=username,
                GroupName=group,
            )
        for group in to_remove:
            logger.info("update_user_groups: removing username=%s from group=%s", username, group)
            client.admin_remove_user_from_group(
                UserPoolId=COGNITO_USER_POOL_ID,
                Username=username,
                GroupName=group,
            )
    except ClientError as exc:
        logger.error("update_user_groups: Cognito error for username=%s — %s", username, exc)
        return _log_response(_error(500, "Failed to update user groups"))

    logger.info("update_user_groups: success for username=%s, groups=%s", username, desired_groups)
    return _log_response(_ok({"message": "User groups updated successfully", "groups": desired_groups}))


def disable_user(username: str, event, context):
    """POST /users/{username}/disable — disable a Cognito user account."""
    logger.info("disable_user called: username=%s", username)
    denied = _require_admin(event)
    if denied:
        return _log_response(denied)

    client = _get_client()
    try:
        client.admin_disable_user(UserPoolId=COGNITO_USER_POOL_ID, Username=username)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "UserNotFoundException":
            logger.warning("disable_user: user not found — username=%s", username)
            return _log_response(_error(404, "User not found"))
        logger.error("disable_user: Cognito error for username=%s — %s", username, exc)
        return _log_response(_error(500, "Failed to disable user"))

    logger.info("disable_user: success for username=%s", username)
    return _log_response(_ok({"message": "User disabled successfully"}))


def enable_user(username: str, event, context):
    """POST /users/{username}/enable — re-enable a disabled Cognito user account."""
    logger.info("enable_user called: username=%s", username)
    denied = _require_admin(event)
    if denied:
        return _log_response(denied)

    client = _get_client()
    try:
        client.admin_enable_user(UserPoolId=COGNITO_USER_POOL_ID, Username=username)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "UserNotFoundException":
            logger.warning("enable_user: user not found — username=%s", username)
            return _log_response(_error(404, "User not found"))
        logger.error("enable_user: Cognito error for username=%s — %s", username, exc)
        return _log_response(_error(500, "Failed to enable user"))

    logger.info("enable_user: success for username=%s", username)
    return _log_response(_ok({"message": "User enabled successfully"}))


def delete_user(username: str, event, context):
    """DELETE /users/{username} — permanently delete a Cognito user."""
    logger.info("delete_user called: username=%s", username)
    denied = _require_admin(event)
    if denied:
        return _log_response(denied)

    client = _get_client()
    try:
        client.admin_delete_user(UserPoolId=COGNITO_USER_POOL_ID, Username=username)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "UserNotFoundException":
            logger.warning("delete_user: user not found — username=%s", username)
            return _log_response(_error(404, "User not found"))
        logger.error("delete_user: Cognito error for username=%s — %s", username, exc)
        return _log_response(_error(500, "Failed to delete user"))

    logger.info("delete_user: success for username=%s", username)
    return _log_response(_no_content())


# ── Router ───────────────────────────────────────────────────────────────────

# Matches /users/{username} where username is everything after the last slash
_USER_PATH_RE = re.compile(r"^/users/([^/]+)$")
_USER_GROUPS_PATH_RE = re.compile(r"^/users/([^/]+)/groups$")
_USER_DISABLE_PATH_RE = re.compile(r"^/users/([^/]+)/disable$")
_USER_ENABLE_PATH_RE = re.compile(r"^/users/([^/]+)/enable$")


def router(event, context):
    """Route incoming requests to the appropriate handler based on path and method."""
    path = event.get("path", "")
    method = event.get("httpMethod", "").upper()

    logger.info("router: path=%s, method=%s", path, method)

    if method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": "",
        }

    # GET /users
    if path == "/users" and method == "GET":
        return list_users(event, context)

    # GET /users/{username}
    m = _USER_PATH_RE.match(path)
    if m and method == "GET":
        return get_user(m.group(1), event, context)

    # DELETE /users/{username}
    if m and method == "DELETE":
        return delete_user(m.group(1), event, context)

    # PUT /users/{username}/groups
    m = _USER_GROUPS_PATH_RE.match(path)
    if m and method == "PUT":
        return update_user_groups(m.group(1), event, context)

    # POST /users/{username}/disable
    m = _USER_DISABLE_PATH_RE.match(path)
    if m and method == "POST":
        return disable_user(m.group(1), event, context)

    # POST /users/{username}/enable
    m = _USER_ENABLE_PATH_RE.match(path)
    if m and method == "POST":
        return enable_user(m.group(1), event, context)

    logger.warning("router: unrecognized path=%s, method=%s", path, method)
    return _log_response(_error(404, f"Endpoint {method} {path} not found"))
