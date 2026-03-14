"""
Acro Hub — Videos Lambda
Generates pre-signed S3 URLs for secure video streaming and uploads.
"""
import json
import logging
import os
import uuid

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

VIDEO_BUCKET = os.environ.get("VIDEO_BUCKET", "acro-hub-videos-dev")
MOVES_TABLE = os.environ.get("MOVES_TABLE", "acro-hub-moves-dev")
PRESIGNED_URL_EXPIRY = 3600  # seconds

_s3 = None
_dynamodb = None
_moves_table = None


def _get_s3():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3")
    return _s3


def _get_moves_table():
    global _dynamodb, _moves_table
    if _moves_table is None:
        _dynamodb = boto3.resource("dynamodb")
        _moves_table = _dynamodb.Table(MOVES_TABLE)
    return _moves_table


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


def _log_response(response: dict) -> dict:
    """Log the HTTP status code of an outgoing response and return it unchanged."""
    logger.info("Returning status %d", response["statusCode"])
    return response


# ── Handlers ─────────────────────────────────────────────────────────────────

def get_video_url(event, context):
    """GET /videos/{moveId}/url — generate a pre-signed URL for viewing a video."""
    move_id = (event.get("pathParameters") or {}).get("moveId")
    logger.info("get_video_url called: move_id=%s", move_id)
    if not move_id:
        logger.warning("get_video_url: missing moveId path parameter")
        return _log_response(_bad_request("moveId path parameter is required"))

    # Look up the move to get the S3 videoKey
    table = _get_moves_table()
    try:
        result = table.get_item(Key={"moveId": move_id})
    except ClientError as exc:
        logger.error("get_video_url: DynamoDB error for move_id=%s — %s", move_id, exc)
        return _log_response(_error(500, "Failed to retrieve move"))

    item = result.get("Item")
    if not item:
        logger.warning("get_video_url: move_id=%s not found", move_id)
        return _log_response(_not_found(f"Move '{move_id}' not found"))

    video_key = item.get("videoKey", "").strip()
    if not video_key:
        logger.warning("get_video_url: no video associated with move_id=%s", move_id)
        return _log_response(_not_found(f"No video associated with move '{move_id}'"))

    logger.info("get_video_url: generating pre-signed URL for move_id=%s, video_key=%s", move_id, video_key)
    s3 = _get_s3()
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": VIDEO_BUCKET, "Key": video_key},
            ExpiresIn=PRESIGNED_URL_EXPIRY,
        )
    except ClientError as exc:
        logger.error("get_video_url: S3 pre-sign error for move_id=%s — %s", move_id, exc)
        return _log_response(_error(500, "Failed to generate video URL"))

    logger.info("get_video_url: pre-signed URL generated for move_id=%s", move_id)
    return _log_response(_ok({"url": url, "expiresIn": PRESIGNED_URL_EXPIRY, "moveId": move_id}))


def get_upload_url(event, context):
    """POST /videos/{moveId}/upload-url — generate a pre-signed PUT URL for uploading a video."""
    move_id = (event.get("pathParameters") or {}).get("moveId")
    logger.info("get_upload_url called: move_id=%s", move_id)
    if not move_id:
        logger.warning("get_upload_url: missing moveId path parameter")
        return _log_response(_bad_request("moveId path parameter is required"))

    # Verify the move exists
    table = _get_moves_table()
    try:
        result = table.get_item(Key={"moveId": move_id})
    except ClientError as exc:
        logger.error("get_upload_url: DynamoDB error for move_id=%s — %s", move_id, exc)
        return _log_response(_error(500, "Failed to retrieve move"))

    if not result.get("Item"):
        logger.warning("get_upload_url: move_id=%s not found", move_id)
        return _log_response(_not_found(f"Move '{move_id}' not found"))

    video_key = f"videos/{move_id}/{uuid.uuid4()}.mp4"
    logger.info("get_upload_url: generating pre-signed upload URL for move_id=%s, video_key=%s", move_id, video_key)

    s3 = _get_s3()
    try:
        upload_url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": VIDEO_BUCKET,
                "Key": video_key,
                "ContentType": "video/mp4",
            },
            ExpiresIn=PRESIGNED_URL_EXPIRY,
        )
    except ClientError as exc:
        logger.error("get_upload_url: S3 pre-sign error for move_id=%s — %s", move_id, exc)
        return _log_response(_error(500, "Failed to generate upload URL"))

    logger.info("get_upload_url: pre-signed upload URL generated for move_id=%s", move_id)

    # Persist the videoKey to DynamoDB so get_video_url can locate the object later
    try:
        table.update_item(
            Key={"moveId": move_id},
            UpdateExpression="SET videoKey = :vk",
            ExpressionAttributeValues={":vk": video_key},
        )
    except ClientError as exc:
        logger.error("get_upload_url: DynamoDB update error for move_id=%s — %s", move_id, exc)
        return _log_response(_error(500, "Failed to persist video key"))

    logger.info("get_upload_url: videoKey persisted to DynamoDB for move_id=%s", move_id)
    return _log_response(
        _ok(
            {
                "uploadUrl": upload_url,
                "videoKey": video_key,
                "expiresIn": PRESIGNED_URL_EXPIRY,
                "moveId": move_id,
            }
        )
    )


# ── Router ───────────────────────────────────────────────────────────────────

def router(event, context):
    """Route incoming requests to the appropriate handler based on path and method."""
    path = event.get("path", "")
    method = event.get("httpMethod", "").upper()

    logger.info("router: path=%s, method=%s", path, method)

    # Route based on path and method
    if path.startswith("/videos/") and path.endswith("/url") and method == "GET":
        return get_video_url(event, context)
    elif path.startswith("/videos/") and path.endswith("/upload-url") and method == "POST":
        return get_upload_url(event, context)
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
