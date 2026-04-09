"""
Acro Hub — User Move Lists Lambda
Allows authenticated users to manage their personal move lists:
  - favourites
  - learned
  - want-to-learn

DynamoDB schema (user-move-lists table):
  hash key:  userId          — Cognito sub from JWT
  range key: listType#moveId — composite, e.g. "favourites#abc-123"
"""
import json
import logging
import os
import re

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "acro-hub-user-move-lists-dev")

_dynamodb = None
_table = None


def _get_table():
    global _dynamodb, _table
    if _table is None:
        _dynamodb = boto3.resource("dynamodb")
        _table = _dynamodb.Table(DYNAMODB_TABLE)
    return _table


# ── Helpers ──────────────────────────────────────────────────────────────────

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "OPTIONS,GET,PUT,DELETE",
    "Content-Type": "application/json",
}

VALID_LIST_TYPES = {"favourites", "learned", "want-to-learn"}


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


def _unauthorized() -> dict:
    return {
        "statusCode": 401,
        "headers": CORS_HEADERS,
        "body": json.dumps({"error": "Authentication required"}),
    }


def _not_found(message: str = "Not found") -> dict:
    return {
        "statusCode": 404,
        "headers": CORS_HEADERS,
        "body": json.dumps({"error": message}),
    }


def _error(status: int, message: str) -> dict:
    return {
        "statusCode": status,
        "headers": CORS_HEADERS,
        "body": json.dumps({"error": message}),
    }


def _log_response(response: dict) -> dict:
    """Log the HTTP status code of an outgoing response and return it unchanged."""
    logger.info("Returning status %d", response["statusCode"])
    return response


def _get_user_id(event: dict) -> str | None:
    """Extract the authenticated user's sub claim from the Cognito authorizer context."""
    try:
        sub = event["requestContext"]["authorizer"]["claims"]["sub"]
        return sub if sub else None
    except (KeyError, TypeError):
        return None


# ── Handlers ─────────────────────────────────────────────────────────────────

def list_moves_in_list(list_type: str, event, context):
    """GET /me/moves/{listType} — return all moves in the given list for the caller."""
    user_id = _get_user_id(event)
    if not user_id:
        logger.warning("list_moves_in_list: missing userId in token")
        return _log_response(_unauthorized())

    logger.info("list_moves_in_list: userId=%s, listType=%s", user_id, list_type)

    table = _get_table()
    try:
        result = table.query(
            KeyConditionExpression=(
                Key("userId").eq(user_id)
                & Key("listType#moveId").begins_with(f"{list_type}#")
            )
        )
    except ClientError as exc:
        logger.error(
            "list_moves_in_list: DynamoDB error for userId=%s, listType=%s — %s",
            user_id, list_type, exc,
        )
        return _log_response(_error(500, "Failed to retrieve list"))

    items = result.get("Items", [])
    while "LastEvaluatedKey" in result:
        try:
            result = table.query(
                KeyConditionExpression=(
                    Key("userId").eq(user_id)
                    & Key("listType#moveId").begins_with(f"{list_type}#")
                ),
                ExclusiveStartKey=result["LastEvaluatedKey"],
            )
            items.extend(result.get("Items", []))
        except ClientError as exc:
            logger.error(
                "list_moves_in_list: DynamoDB pagination error for userId=%s, listType=%s — %s",
                user_id, list_type, exc,
            )
            break

    move_ids = [item["listType#moveId"].split("#", 1)[1] for item in items]
    logger.info(
        "list_moves_in_list: userId=%s, listType=%s — returning %d move(s)",
        user_id, list_type, len(move_ids),
    )
    return _log_response(_ok({"listType": list_type, "moveIds": move_ids, "count": len(move_ids)}))


def add_move_to_list(list_type: str, move_id: str, event, context):
    """PUT /me/moves/{listType}/{moveId} — add a move to the caller's list."""
    user_id = _get_user_id(event)
    if not user_id:
        logger.warning("add_move_to_list: missing userId in token")
        return _log_response(_unauthorized())

    logger.info(
        "add_move_to_list: userId=%s, listType=%s, moveId=%s",
        user_id, list_type, move_id,
    )

    table = _get_table()
    item = {
        "userId": user_id,
        "listType#moveId": f"{list_type}#{move_id}",
        "listType": list_type,
        "moveId": move_id,
    }

    try:
        table.put_item(Item=item)
    except ClientError as exc:
        logger.error(
            "add_move_to_list: DynamoDB error for userId=%s, listType=%s, moveId=%s — %s",
            user_id, list_type, move_id, exc,
        )
        return _log_response(_error(500, "Failed to add move to list"))

    logger.info(
        "add_move_to_list: success — userId=%s, listType=%s, moveId=%s",
        user_id, list_type, move_id,
    )
    return _log_response(_ok({"listType": list_type, "moveId": move_id}))


def remove_move_from_list(list_type: str, move_id: str, event, context):
    """DELETE /me/moves/{listType}/{moveId} — remove a move from the caller's list."""
    user_id = _get_user_id(event)
    if not user_id:
        logger.warning("remove_move_from_list: missing userId in token")
        return _log_response(_unauthorized())

    logger.info(
        "remove_move_from_list: userId=%s, listType=%s, moveId=%s",
        user_id, list_type, move_id,
    )

    table = _get_table()
    try:
        table.delete_item(
            Key={
                "userId": user_id,
                "listType#moveId": f"{list_type}#{move_id}",
            }
        )
    except ClientError as exc:
        logger.error(
            "remove_move_from_list: DynamoDB error for userId=%s, listType=%s, moveId=%s — %s",
            user_id, list_type, move_id, exc,
        )
        return _log_response(_error(500, "Failed to remove move from list"))

    logger.info(
        "remove_move_from_list: success — userId=%s, listType=%s, moveId=%s",
        user_id, list_type, move_id,
    )
    return _log_response(_no_content())


# ── Router ───────────────────────────────────────────────────────────────────

# /me/moves/{listType}
_LIST_PATH_RE = re.compile(r"^/me/moves/([^/]+)$")
# /me/moves/{listType}/{moveId}
_MOVE_PATH_RE = re.compile(r"^/me/moves/([^/]+)/([^/]+)$")


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

    # GET /me/moves/{listType}
    m = _LIST_PATH_RE.match(path)
    if m and method == "GET":
        list_type = m.group(1)
        if list_type not in VALID_LIST_TYPES:
            logger.warning("router: invalid listType=%s", list_type)
            return _log_response(
                _bad_request(
                    f"listType must be one of: {', '.join(sorted(VALID_LIST_TYPES))}"
                )
            )
        return list_moves_in_list(list_type, event, context)

    # PUT /me/moves/{listType}/{moveId} or DELETE /me/moves/{listType}/{moveId}
    m = _MOVE_PATH_RE.match(path)
    if m:
        list_type = m.group(1)
        move_id = m.group(2)
        if list_type not in VALID_LIST_TYPES:
            logger.warning("router: invalid listType=%s", list_type)
            return _log_response(
                _bad_request(
                    f"listType must be one of: {', '.join(sorted(VALID_LIST_TYPES))}"
                )
            )
        if method == "PUT":
            return add_move_to_list(list_type, move_id, event, context)
        if method == "DELETE":
            return remove_move_from_list(list_type, move_id, event, context)

    logger.warning("router: unrecognized path=%s, method=%s", path, method)
    return _log_response(_error(404, f"Endpoint {method} {path} not found"))
