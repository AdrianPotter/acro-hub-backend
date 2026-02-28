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


# ── Handlers ─────────────────────────────────────────────────────────────────

def track_event(event, context):
    """POST /events — record a new operational event."""
    try:
        body = _parse_body(event)
    except json.JSONDecodeError:
        return _bad_request("Invalid JSON body")

    event_type = body.get("eventType", "").strip()
    if not event_type:
        return _bad_request("eventType is required")
    if event_type not in VALID_EVENT_TYPES:
        return _bad_request(
            f"eventType must be one of: {', '.join(sorted(VALID_EVENT_TYPES))}"
        )

    user_id = _get_user_id(event)
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
        logger.error("DynamoDB error during track_event: %s", exc)
        return _error(500, "Failed to record event")

    return _created(record)


def list_events(event, context):
    """GET /events — list events with optional filters (userId, eventType, from, to)."""
    params = event.get("queryStringParameters") or {}

    filter_user_id = params.get("userId")
    filter_event_type = params.get("eventType")
    filter_from = params.get("from")
    filter_to = params.get("to")

    table = _get_table()

    try:
        # Use GSI if filtering by userId
        if filter_user_id:
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
        logger.error("DynamoDB error during list_events: %s", exc)
        return _error(500, "Failed to retrieve events")

    return _ok({"events": items, "count": len(items)})
