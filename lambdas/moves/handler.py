"""
Acro Hub — Moves Lambda
CRUD operations for acrobatic move metadata stored in DynamoDB.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "acro-hub-moves-dev")

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
    "Access-Control-Allow-Methods": "OPTIONS,POST,GET,PUT,DELETE",
    "Content-Type": "application/json",
}

VALID_DIFFICULTIES = {"easy", "medium", "hard", "expert"}
VALID_CATEGORIES = {"acrobalance", "hand-to-hand", "icarian", "washing-machine"}


def _ok(body: dict) -> dict:
    return {"statusCode": 200, "headers": CORS_HEADERS, "body": json.dumps(body)}


def _created(body: dict) -> dict:
    return {"statusCode": 201, "headers": CORS_HEADERS, "body": json.dumps(body)}


def _bad_request(message: str) -> dict:
    return {
        "statusCode": 400,
        "headers": CORS_HEADERS,
        "body": json.dumps({"error": message}),
    }


def _not_found(message: str = "Move not found") -> dict:
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


def _parse_body(event: dict) -> dict:
    raw = event.get("body") or "{}"
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Handlers ─────────────────────────────────────────────────────────────────

def list_moves(event, context):
    """GET /moves — return all moves."""
    table = _get_table()
    try:
        result = table.scan()
    except ClientError as exc:
        logger.error("DynamoDB error during list_moves: %s", exc)
        return _error(500, "Failed to retrieve moves")

    items = result.get("Items", [])
    # Handle DynamoDB pagination
    while "LastEvaluatedKey" in result:
        try:
            result = table.scan(ExclusiveStartKey=result["LastEvaluatedKey"])
            items.extend(result.get("Items", []))
        except ClientError as exc:
            logger.error("DynamoDB pagination error: %s", exc)
            break

    return _ok({"moves": items, "count": len(items)})


def get_move(event, context):
    """GET /moves/{id} — return a single move by moveId."""
    move_id = (event.get("pathParameters") or {}).get("id")
    if not move_id:
        return _bad_request("moveId path parameter is required")

    table = _get_table()
    try:
        result = table.get_item(Key={"moveId": move_id})
    except ClientError as exc:
        logger.error("DynamoDB error during get_move: %s", exc)
        return _error(500, "Failed to retrieve move")

    item = result.get("Item")
    if not item:
        return _not_found(f"Move '{move_id}' not found")

    return _ok(item)


def create_move(event, context):
    """POST /moves — create a new move."""
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _bad_request("Invalid JSON body")

    name = body.get("name", "").strip()
    if not name:
        return _bad_request("name is required")

    difficulty = body.get("difficulty", "easy")
    if difficulty not in VALID_DIFFICULTIES:
        return _bad_request(f"difficulty must be one of: {', '.join(sorted(VALID_DIFFICULTIES))}")

    category = body.get("category", "acrobalance")
    if category not in VALID_CATEGORIES:
        return _bad_request(f"category must be one of: {', '.join(sorted(VALID_CATEGORIES))}")

    now = _now_iso()
    move = {
        "moveId": str(uuid.uuid4()),
        "name": name,
        "description": body.get("description", ""),
        "difficulty": difficulty,
        "category": category,
        "videoKey": body.get("videoKey", ""),
        "tags": body.get("tags", []),
        "createdAt": now,
        "updatedAt": now,
    }

    table = _get_table()
    try:
        table.put_item(Item=move)
    except ClientError as exc:
        logger.error("DynamoDB error during create_move: %s", exc)
        return _error(500, "Failed to create move")

    return _created(move)


def update_move(event, context):
    """PUT /moves/{id} — update an existing move."""
    move_id = (event.get("pathParameters") or {}).get("id")
    if not move_id:
        return _bad_request("moveId path parameter is required")

    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _bad_request("Invalid JSON body")

    table = _get_table()

    # Verify the move exists
    try:
        existing = table.get_item(Key={"moveId": move_id})
    except ClientError as exc:
        logger.error("DynamoDB error checking move existence: %s", exc)
        return _error(500, "Failed to retrieve move")

    if not existing.get("Item"):
        return _not_found(f"Move '{move_id}' not found")

    # Build update expression dynamically from provided fields
    updatable = ["name", "description", "difficulty", "category", "videoKey", "tags"]
    update_parts = []
    expr_names = {}
    expr_values = {}

    for field in updatable:
        if field in body:
            if field == "difficulty" and body[field] not in VALID_DIFFICULTIES:
                return _bad_request(
                    f"difficulty must be one of: {', '.join(sorted(VALID_DIFFICULTIES))}"
                )
            if field == "category" and body[field] not in VALID_CATEGORIES:
                return _bad_request(
                    f"category must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
                )
            placeholder = f"#f_{field}"
            value_key = f":v_{field}"
            update_parts.append(f"{placeholder} = {value_key}")
            expr_names[placeholder] = field
            expr_values[value_key] = body[field]

    # Always update updatedAt
    update_parts.append("#f_updatedAt = :v_updatedAt")
    expr_names["#f_updatedAt"] = "updatedAt"
    expr_values[":v_updatedAt"] = _now_iso()

    update_expression = "SET " + ", ".join(update_parts)

    try:
        result = table.update_item(
            Key={"moveId": move_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        logger.error("DynamoDB error during update_move: %s", exc)
        return _error(500, "Failed to update move")

    return _ok(result.get("Attributes", {}))


def delete_move(event, context):
    """DELETE /moves/{id} — delete a move."""
    move_id = (event.get("pathParameters") or {}).get("id")
    if not move_id:
        return _bad_request("moveId path parameter is required")

    table = _get_table()

    # Verify the move exists before deleting
    try:
        existing = table.get_item(Key={"moveId": move_id})
    except ClientError as exc:
        logger.error("DynamoDB error checking move existence: %s", exc)
        return _error(500, "Failed to retrieve move")

    if not existing.get("Item"):
        return _not_found(f"Move '{move_id}' not found")

    try:
        table.delete_item(Key={"moveId": move_id})
    except ClientError as exc:
        logger.error("DynamoDB error during delete_move: %s", exc)
        return _error(500, "Failed to delete move")

    return _ok({"message": f"Move '{move_id}' deleted successfully"})
