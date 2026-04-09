"""
Acro Hub — Moves Lambda
CRUD operations for acrobatic move metadata stored in DynamoDB.
Includes directed-edge graph operations (Option 2 — global DAG via separate
edge table).

Edge table data shape:
    { fromMoveId (hash), toMoveId (range), createdAt, createdBy }
    GSI "toMoveId-fromMoveId-index": hash=toMoveId, range=fromMoveId
        (supports efficient prerequisite reverse-lookups)
"""
import json
import logging
import os
import uuid
from collections import deque
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "acro-hub-moves-dev")
EDGES_TABLE = os.environ.get("EDGES_TABLE", "acro-hub-move-edges-dev")

_dynamodb = None
_table = None
_edges_table = None


def _get_table():
    global _dynamodb, _table
    if _table is None:
        _dynamodb = boto3.resource("dynamodb")
        _table = _dynamodb.Table(DYNAMODB_TABLE)
    return _table


def _get_edges_table():
    global _dynamodb, _edges_table
    if _edges_table is None:
        if _dynamodb is None:
            _dynamodb = boto3.resource("dynamodb")
        _edges_table = _dynamodb.Table(EDGES_TABLE)
    return _edges_table


# ── Helpers ──────────────────────────────────────────────────────────────────

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "OPTIONS,POST,GET,PUT,PATCH,DELETE",
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


def _log_response(response: dict) -> dict:
    """Log the HTTP status code of an outgoing response and return it unchanged."""
    logger.info("Returning status %d", response["statusCode"])
    return response


def _get_user_groups(event: dict) -> set:
    """Extract Cognito group memberships from the JWT claims in the request context."""
    claims = (
        (event.get("requestContext") or {})
        .get("authorizer", {})
        .get("claims", {})
    )
    groups_str = claims.get("cognito:groups", "")
    if not groups_str:
        return set()
    return set(groups_str.split(","))


def _forbidden(message: str = "You do not have permission to perform this action") -> dict:
    return {
        "statusCode": 403,
        "headers": CORS_HEADERS,
        "body": json.dumps({"error": message}),
    }


def _conflict(message: str) -> dict:
    return {
        "statusCode": 409,
        "headers": CORS_HEADERS,
        "body": json.dumps({"error": message}),
    }


UPLOAD_GROUPS = {"contributors", "curators", "admins"}
EDIT_DELETE_GROUPS = {"curators", "admins"}


# ── Handlers ─────────────────────────────────────────────────────────────────

def list_moves(event, context):
    """GET /moves — return all moves."""
    logger.info("list_moves called")
    table = _get_table()
    try:
        result = table.scan()
    except ClientError as exc:
        logger.error("list_moves: DynamoDB scan failed — %s", exc)
        return _log_response(_error(500, "Failed to retrieve moves"))

    items = result.get("Items", [])
    # Handle DynamoDB pagination
    while "LastEvaluatedKey" in result:
        try:
            result = table.scan(ExclusiveStartKey=result["LastEvaluatedKey"])
            items.extend(result.get("Items", []))
        except ClientError as exc:
            logger.error("list_moves: DynamoDB pagination error — %s", exc)
            break

    logger.info("list_moves: returning %d move(s)", len(items))
    return _log_response(_ok({"moves": items, "count": len(items)}))


def get_move(event, context):
    """GET /moves/{id} — return a single move by moveId."""
    move_id = (event.get("pathParameters") or {}).get("id")
    logger.info("get_move called: move_id=%s", move_id)
    if not move_id:
        logger.warning("get_move: missing moveId path parameter")
        return _log_response(_bad_request("moveId path parameter is required"))

    table = _get_table()
    try:
        result = table.get_item(Key={"moveId": move_id})
    except ClientError as exc:
        logger.error("get_move: DynamoDB error for move_id=%s — %s", move_id, exc)
        return _log_response(_error(500, "Failed to retrieve move"))

    item = result.get("Item")
    if not item:
        logger.warning("get_move: move_id=%s not found", move_id)
        return _log_response(_not_found(f"Move '{move_id}' not found"))

    logger.info("get_move: found move_id=%s", move_id)
    return _log_response(_ok(item))


def create_move(event, context):
    """POST /moves — create a new move."""
    logger.info("create_move called")

    user_groups = _get_user_groups(event)
    if not user_groups.intersection(UPLOAD_GROUPS):
        logger.warning("create_move: forbidden — user groups=%s", user_groups)
        return _log_response(_forbidden())

    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        logger.warning("create_move: invalid JSON body")
        return _log_response(_bad_request("Invalid JSON body"))

    name = body.get("name", "").strip()
    if not name:
        logger.warning("create_move: missing required field — name")
        return _log_response(_bad_request("name is required"))

    difficulty = body.get("difficulty", "easy")
    if difficulty not in VALID_DIFFICULTIES:
        logger.warning("create_move: invalid difficulty=%s", difficulty)
        return _log_response(_bad_request(f"difficulty must be one of: {', '.join(sorted(VALID_DIFFICULTIES))}"))

    category = body.get("category", "acrobalance")
    if category not in VALID_CATEGORIES:
        logger.warning("create_move: invalid category=%s", category)
        return _log_response(_bad_request(f"category must be one of: {', '.join(sorted(VALID_CATEGORIES))}"))

    logger.info("create_move: name=%s, difficulty=%s, category=%s", name, difficulty, category)
    now = _now_iso()
    move = {
        "moveId": str(uuid.uuid4()),
        "name": name,
        "description": body.get("description", ""),
        "difficulty": difficulty,
        "category": category,
        "videoKey": body.get("videoKey", ""),
        "tags": body.get("tags", []),
        "alternateNames": body.get("alternateNames", []),
        "createdAt": now,
        "updatedAt": now,
    }

    table = _get_table()
    try:
        table.put_item(Item=move)
    except ClientError as exc:
        logger.error("create_move: DynamoDB error for name=%s — %s", name, exc)
        return _log_response(_error(500, "Failed to create move"))

    logger.info("create_move: created move_id=%s, name=%s", move["moveId"], name)
    return _log_response(_created(move))


def update_move(event, context):
    """PUT /moves/{id} — update an existing move."""
    move_id = (event.get("pathParameters") or {}).get("id")
    logger.info("update_move called: move_id=%s", move_id)

    user_groups = _get_user_groups(event)
    if not user_groups.intersection(EDIT_DELETE_GROUPS):
        logger.warning("update_move: forbidden — user groups=%s", user_groups)
        return _log_response(_forbidden())

    if not move_id:
        logger.warning("update_move: missing moveId path parameter")
        return _log_response(_bad_request("moveId path parameter is required"))

    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        logger.warning("update_move: invalid JSON body for move_id=%s", move_id)
        return _log_response(_bad_request("Invalid JSON body"))

    table = _get_table()

    # Verify the move exists
    try:
        existing = table.get_item(Key={"moveId": move_id})
    except ClientError as exc:
        logger.error("update_move: DynamoDB error checking existence of move_id=%s — %s", move_id, exc)
        return _log_response(_error(500, "Failed to retrieve move"))

    if not existing.get("Item"):
        logger.warning("update_move: move_id=%s not found", move_id)
        return _log_response(_not_found(f"Move '{move_id}' not found"))

    # Build update expression dynamically from provided fields
    updatable = ["name", "description", "difficulty", "category", "videoKey", "tags", "alternateNames"]
    update_parts = []
    expr_names = {}
    expr_values = {}

    for field in updatable:
        if field in body:
            if field == "difficulty" and body[field] not in VALID_DIFFICULTIES:
                logger.warning("update_move: invalid difficulty=%s for move_id=%s", body[field], move_id)
                return _log_response(
                    _bad_request(
                        f"difficulty must be one of: {', '.join(sorted(VALID_DIFFICULTIES))}"
                    )
                )
            if field == "category" and body[field] not in VALID_CATEGORIES:
                logger.warning("update_move: invalid category=%s for move_id=%s", body[field], move_id)
                return _log_response(
                    _bad_request(
                        f"category must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
                    )
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

    logger.info("update_move: updating fields=%s for move_id=%s", list(expr_names.values()), move_id)
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
        logger.error("update_move: DynamoDB error for move_id=%s — %s", move_id, exc)
        return _log_response(_error(500, "Failed to update move"))

    logger.info("update_move: successful for move_id=%s", move_id)
    return _log_response(_ok(result.get("Attributes", {})))


def delete_move(event, context):
    """DELETE /moves/{id} — delete a move."""
    move_id = (event.get("pathParameters") or {}).get("id")
    logger.info("delete_move called: move_id=%s", move_id)

    user_groups = _get_user_groups(event)
    if not user_groups.intersection(EDIT_DELETE_GROUPS):
        logger.warning("delete_move: forbidden — user groups=%s", user_groups)
        return _log_response(_forbidden())

    if not move_id:
        logger.warning("delete_move: missing moveId path parameter")
        return _log_response(_bad_request("moveId path parameter is required"))

    table = _get_table()

    # Verify the move exists before deleting
    try:
        existing = table.get_item(Key={"moveId": move_id})
    except ClientError as exc:
        logger.error("delete_move: DynamoDB error checking existence of move_id=%s — %s", move_id, exc)
        return _log_response(_error(500, "Failed to retrieve move"))

    if not existing.get("Item"):
        logger.warning("delete_move: move_id=%s not found", move_id)
        return _log_response(_not_found(f"Move '{move_id}' not found"))

    try:
        table.delete_item(Key={"moveId": move_id})
    except ClientError as exc:
        logger.error("delete_move: DynamoDB error for move_id=%s — %s", move_id, exc)
        return _log_response(_error(500, "Failed to delete move"))

    logger.info("delete_move: successfully deleted move_id=%s", move_id)
    return _log_response(_ok({"message": f"Move '{move_id}' deleted successfully"}))


# ── DAG helpers ───────────────────────────────────────────────────────────────

def _would_create_cycle(from_move_id: str, to_move_id: str) -> bool:
    """
    Return True if adding the edge from_move_id → to_move_id would create a
    cycle in the global move graph.

    Self-loops are always rejected.  Otherwise we BFS from to_move_id following
    outgoing edges; if we reach from_move_id the edge would close a cycle.
    """
    if from_move_id == to_move_id:
        return True

    edges_table = _get_edges_table()
    visited = {to_move_id}
    queue = deque([to_move_id])

    while queue:
        current = queue.popleft()
        try:
            result = edges_table.query(
                KeyConditionExpression=Key("fromMoveId").eq(current)
            )
        except ClientError as exc:
            logger.error("_would_create_cycle: DynamoDB error — %s", exc)
            return False

        for item in result.get("Items", []):
            next_id = item["toMoveId"]
            if next_id == from_move_id:
                return True
            if next_id not in visited:
                visited.add(next_id)
                queue.append(next_id)

    return False


# ── Edge handlers ─────────────────────────────────────────────────────────────

def get_prerequisites(event, context):
    """GET /moves/{id}/prerequisites — moves that must be done before this one."""
    move_id = (event.get("pathParameters") or {}).get("id")
    logger.info("get_prerequisites called: move_id=%s", move_id)
    if not move_id:
        return _log_response(_bad_request("moveId path parameter is required"))

    # Verify the move exists
    table = _get_table()
    try:
        result = table.get_item(Key={"moveId": move_id})
    except ClientError as exc:
        logger.error("get_prerequisites: DynamoDB error — %s", exc)
        return _log_response(_error(500, "Failed to retrieve move"))
    if not result.get("Item"):
        return _log_response(_not_found(f"Move '{move_id}' not found"))

    # Query edges where toMoveId = move_id (via GSI)
    edges_table = _get_edges_table()
    try:
        edge_result = edges_table.query(
            IndexName="toMoveId-fromMoveId-index",
            KeyConditionExpression=Key("toMoveId").eq(move_id),
        )
    except ClientError as exc:
        logger.error("get_prerequisites: DynamoDB edge query error — %s", exc)
        return _log_response(_error(500, "Failed to retrieve prerequisites"))

    from_ids = [e["fromMoveId"] for e in edge_result.get("Items", [])]

    # Batch-fetch the prerequisite move objects
    moves = []
    for from_id in from_ids:
        try:
            m = table.get_item(Key={"moveId": from_id})
            if m.get("Item"):
                moves.append(m["Item"])
        except ClientError as exc:
            logger.error("get_prerequisites: error fetching move %s — %s", from_id, exc)

    logger.info("get_prerequisites: move_id=%s has %d prerequisite(s)", move_id, len(moves))
    return _log_response(_ok({"moves": moves, "count": len(moves)}))


def get_next(event, context):
    """GET /moves/{id}/next — moves that can be done after this one."""
    move_id = (event.get("pathParameters") or {}).get("id")
    logger.info("get_next called: move_id=%s", move_id)
    if not move_id:
        return _log_response(_bad_request("moveId path parameter is required"))

    # Verify the move exists
    table = _get_table()
    try:
        result = table.get_item(Key={"moveId": move_id})
    except ClientError as exc:
        logger.error("get_next: DynamoDB error — %s", exc)
        return _log_response(_error(500, "Failed to retrieve move"))
    if not result.get("Item"):
        return _log_response(_not_found(f"Move '{move_id}' not found"))

    # Query edges where fromMoveId = move_id
    edges_table = _get_edges_table()
    try:
        edge_result = edges_table.query(
            KeyConditionExpression=Key("fromMoveId").eq(move_id)
        )
    except ClientError as exc:
        logger.error("get_next: DynamoDB edge query error — %s", exc)
        return _log_response(_error(500, "Failed to retrieve next moves"))

    to_ids = [e["toMoveId"] for e in edge_result.get("Items", [])]

    # Batch-fetch the next move objects
    moves = []
    for to_id in to_ids:
        try:
            m = table.get_item(Key={"moveId": to_id})
            if m.get("Item"):
                moves.append(m["Item"])
        except ClientError as exc:
            logger.error("get_next: error fetching move %s — %s", to_id, exc)

    logger.info("get_next: move_id=%s has %d next move(s)", move_id, len(moves))
    return _log_response(_ok({"moves": moves, "count": len(moves)}))


def put_edge(event, context):
    """PUT /moves/{id}/next/{toId} — add a directed edge (curators/admins only)."""
    params = event.get("pathParameters") or {}
    from_move_id = params.get("id")
    to_move_id = params.get("toId")
    logger.info("put_edge called: from=%s, to=%s", from_move_id, to_move_id)

    user_groups = _get_user_groups(event)
    if not user_groups.intersection(EDIT_DELETE_GROUPS):
        logger.warning("put_edge: forbidden — user groups=%s", user_groups)
        return _log_response(_forbidden())

    if not from_move_id or not to_move_id:
        return _log_response(_bad_request("fromMoveId and toMoveId path parameters are required"))

    # Verify both moves exist
    table = _get_table()
    for move_id, label in [(from_move_id, "fromMoveId"), (to_move_id, "toMoveId")]:
        try:
            result = table.get_item(Key={"moveId": move_id})
        except ClientError as exc:
            logger.error("put_edge: DynamoDB error checking move %s — %s", move_id, exc)
            return _log_response(_error(500, "Failed to verify move"))
        if not result.get("Item"):
            return _log_response(_not_found(f"Move '{move_id}' not found"))

    # Cycle detection
    if _would_create_cycle(from_move_id, to_move_id):
        logger.warning("put_edge: cycle detected for from=%s to=%s", from_move_id, to_move_id)
        return _log_response(_conflict("Adding this edge would create a cycle in the move graph"))

    edge_item = {
        "fromMoveId": from_move_id,
        "toMoveId": to_move_id,
        "createdAt": _now_iso(),
    }

    edges_table = _get_edges_table()
    try:
        edges_table.put_item(Item=edge_item)
    except ClientError as exc:
        logger.error("put_edge: DynamoDB error — %s", exc)
        return _log_response(_error(500, "Failed to create edge"))

    logger.info("put_edge: edge created from=%s to=%s", from_move_id, to_move_id)
    return _log_response(_created(edge_item))


def delete_edge(event, context):
    """DELETE /moves/{id}/next/{toId} — remove a directed edge (curators/admins only)."""
    params = event.get("pathParameters") or {}
    from_move_id = params.get("id")
    to_move_id = params.get("toId")
    logger.info("delete_edge called: from=%s, to=%s", from_move_id, to_move_id)

    user_groups = _get_user_groups(event)
    if not user_groups.intersection(EDIT_DELETE_GROUPS):
        logger.warning("delete_edge: forbidden — user groups=%s", user_groups)
        return _log_response(_forbidden())

    if not from_move_id or not to_move_id:
        return _log_response(_bad_request("fromMoveId and toMoveId path parameters are required"))

    edges_table = _get_edges_table()

    # Verify the edge exists before deleting
    try:
        existing = edges_table.get_item(Key={"fromMoveId": from_move_id, "toMoveId": to_move_id})
    except ClientError as exc:
        logger.error("delete_edge: DynamoDB error checking edge — %s", exc)
        return _log_response(_error(500, "Failed to retrieve edge"))

    if not existing.get("Item"):
        return _log_response(_not_found(f"Edge '{from_move_id}' -> '{to_move_id}' not found"))

    try:
        edges_table.delete_item(Key={"fromMoveId": from_move_id, "toMoveId": to_move_id})
    except ClientError as exc:
        logger.error("delete_edge: DynamoDB error — %s", exc)
        return _log_response(_error(500, "Failed to delete edge"))

    logger.info("delete_edge: edge removed from=%s to=%s", from_move_id, to_move_id)
    return _log_response(_ok({"message": f"Edge '{from_move_id}' -> '{to_move_id}' removed"}))


# ── Router ───────────────────────────────────────────────────────────────────

def router(event, context):
    """Route incoming requests to the appropriate handler based on path and method."""
    path = event.get("path", "")
    method = event.get("httpMethod", "").upper()

    logger.info("router: path=%s, method=%s", path, method)

    # CORS preflight
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    # Parse path segments for sub-resource routing
    parts = [p for p in path.split("/") if p]
    n = len(parts)

    # /moves
    if n == 1 and parts[0] == "moves":
        if method == "GET":
            return list_moves(event, context)
        if method == "POST":
            return create_move(event, context)

    # /moves/{id}
    elif n == 2 and parts[0] == "moves":
        if method == "GET":
            return get_move(event, context)
        if method in ("PUT", "PATCH"):
            return update_move(event, context)
        if method == "DELETE":
            return delete_move(event, context)

    # /moves/{id}/prerequisites  or  /moves/{id}/next
    elif n == 3 and parts[0] == "moves":
        if parts[2] == "prerequisites" and method == "GET":
            return get_prerequisites(event, context)
        if parts[2] == "next" and method == "GET":
            return get_next(event, context)

    # /moves/{fromId}/next/{toId}
    elif n == 4 and parts[0] == "moves" and parts[2] == "next":
        if method == "PUT":
            return put_edge(event, context)
        if method == "DELETE":
            return delete_edge(event, context)

    logger.warning("router: unrecognized path=%s, method=%s", path, method)
    return _log_response(_error(404, f"Endpoint {method} {path} not found"))
