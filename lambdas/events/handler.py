"""
Acro Hub — Events Lambda
Records and retrieves operational events (logins, move views, etc.) in DynamoDB.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

EVENTS_TABLE = os.environ.get("EVENTS_TABLE", "acro-hub-events-dev")

_dynamodb = None
_table = None


def _get_table():
    global _dynamodb, _table
    if _table is None:
        _dynamodb = boto3.resource("dynamodb")
        _table = _dynamodb.Table(EVENTS_TABLE)
    return _table


# ── Helpers ──────────────────────────────────────────────────────────────────

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "OPTIONS,POST,GET",
    "Content-Type": "application/json",
}

VALID_EVENT_TYPES = {"login", "logout", "move_view", "move_upload", "registration"}


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


def _get_user_id(event: dict) -> str:
    """Extract the authenticated user's sub claim from the Cognito authorizer context."""
    try:
        return event["requestContext"]["authorizer"]["claims"]["sub"]
    except (KeyError, TypeError):
        return "unknown"


def _log_response(response: dict) -> dict:
    """Log the HTTP status code of an outgoing response and return it unchanged."""
    logger.info("Returning status %d", response["statusCode"])
    return response


# ── Handlers ─────────────────────────────────────────────────────────────────

def track_event(event, context):
    """POST /events — record a new operational event."""
    logger.info("track_event called")
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        logger.warning("track_event: invalid JSON body")
        return _log_response(_bad_request("Invalid JSON body"))

    event_type = body.get("eventType", "").strip()
    if not event_type:
        logger.warning("track_event: missing required field — eventType")
        return _log_response(_bad_request("eventType is required"))
    if event_type not in VALID_EVENT_TYPES:
        logger.warning("track_event: invalid eventType=%s", event_type)
        return _log_response(
            _bad_request(
                f"eventType must be one of: {', '.join(sorted(VALID_EVENT_TYPES))}"
            )
        )

    user_id = _get_user_id(event)
    logger.info("track_event: eventType=%s, userId=%s", event_type, user_id)
    timestamp = _now_iso()

    record = {
        "eventId": str(uuid.uuid4()),
        "eventType": event_type,
        "userId": user_id,
        "resourceId": body.get("resourceId", ""),
        "timestamp": timestamp,
        "metadata": body.get("metadata", {}),
    }

    table = _get_table()
    try:
        table.put_item(Item=record)
    except ClientError as exc:
        logger.error("track_event: DynamoDB error for eventType=%s, userId=%s — %s", event_type, user_id, exc)
        return _log_response(_error(500, "Failed to record event"))

    logger.info("track_event: recorded eventId=%s, eventType=%s, userId=%s", record["eventId"], event_type, user_id)
    return _log_response(_created(record))


def list_events(event, context):
    """GET /events — list events with optional filters (userId, eventType, from, to)."""
    params = event.get("queryStringParameters") or {}

    filter_user_id = params.get("userId")
    filter_event_type = params.get("eventType")
    filter_from = params.get("from")
    filter_to = params.get("to")

    logger.info(
        "list_events called: userId=%s, eventType=%s, from=%s, to=%s",
        filter_user_id, filter_event_type, filter_from, filter_to,
    )

    table = _get_table()

    try:
        # Use GSI if filtering by userId
        if filter_user_id:
            logger.info("list_events: using userId-timestamp GSI for userId=%s", filter_user_id)
            query_kwargs = {
                "IndexName": "userId-timestamp-index",
                "KeyConditionExpression": Key("userId").eq(filter_user_id),
            }
            if filter_from and filter_to:
                query_kwargs["KeyConditionExpression"] &= Key("timestamp").between(
                    filter_from, filter_to
                )
            elif filter_from:
                query_kwargs["KeyConditionExpression"] &= Key("timestamp").gte(filter_from)
            elif filter_to:
                query_kwargs["KeyConditionExpression"] &= Key("timestamp").lte(filter_to)

            if filter_event_type:
                query_kwargs["FilterExpression"] = Attr("eventType").eq(filter_event_type)

            result = table.query(**query_kwargs)
            items = result.get("Items", [])
            while "LastEvaluatedKey" in result:
                query_kwargs["ExclusiveStartKey"] = result["LastEvaluatedKey"]
                result = table.query(**query_kwargs)
                items.extend(result.get("Items", []))

        elif filter_event_type:
            logger.info("list_events: using eventType-timestamp GSI for eventType=%s", filter_event_type)
            # Use GSI for eventType filtering
            query_kwargs = {
                "IndexName": "eventType-timestamp-index",
                "KeyConditionExpression": Key("eventType").eq(filter_event_type),
            }
            if filter_from and filter_to:
                query_kwargs["KeyConditionExpression"] &= Key("timestamp").between(
                    filter_from, filter_to
                )
            elif filter_from:
                query_kwargs["KeyConditionExpression"] &= Key("timestamp").gte(filter_from)
            elif filter_to:
                query_kwargs["KeyConditionExpression"] &= Key("timestamp").lte(filter_to)

            result = table.query(**query_kwargs)
            items = result.get("Items", [])
            while "LastEvaluatedKey" in result:
                query_kwargs["ExclusiveStartKey"] = result["LastEvaluatedKey"]
                result = table.query(**query_kwargs)
                items.extend(result.get("Items", []))

        else:
            logger.info("list_events: performing full table scan (no userId or eventType filter)")
            # Full scan with optional date range filter
            scan_kwargs: dict = {}
            filter_exprs = []
            expr_values: dict = {}

            if filter_from:
                filter_exprs.append(Attr("timestamp").gte(filter_from))
            if filter_to:
                filter_exprs.append(Attr("timestamp").lte(filter_to))

            if filter_exprs:
                combined = filter_exprs[0]
                for expr in filter_exprs[1:]:
                    combined = combined & expr
                scan_kwargs["FilterExpression"] = combined

            result = table.scan(**scan_kwargs)
            items = result.get("Items", [])
            while "LastEvaluatedKey" in result:
                scan_kwargs["ExclusiveStartKey"] = result["LastEvaluatedKey"]
                result = table.scan(**scan_kwargs)
                items.extend(result.get("Items", []))

    except ClientError as exc:
        logger.error("list_events: DynamoDB error — %s", exc)
        return _log_response(_error(500, "Failed to retrieve events"))

    logger.info("list_events: returning %d event(s)", len(items))
    return _log_response(_ok({"events": items, "count": len(items)}))


# ── Router ───────────────────────────────────────────────────────────────────

def router(event, context):
    """Route incoming requests to the appropriate handler based on path and method."""
    path = event.get("path", "")
    method = event.get("httpMethod", "").upper()

    logger.info("router: path=%s, method=%s", path, method)

    # Route based on path and method
    if path == "/events" and method == "POST":
        return track_event(event, context)
    elif path == "/events" and method == "GET":
        return list_events(event, context)
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
