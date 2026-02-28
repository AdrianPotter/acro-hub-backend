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


# ── Handlers ─────────────────────────────────────────────────────────────────

def get_video_url(event, context):
    """GET /videos/{moveId}/url — generate a pre-signed URL for viewing a video."""
    move_id = (event.get("pathParameters") or {}).get("moveId")
    if not move_id:
        return _bad_request("moveId path parameter is required")

    # Look up the move to get the S3 videoKey
    table = _get_moves_table()
    try:
        result = table.get_item(Key={"moveId": move_id})
    except ClientError as exc:
        logger.error("DynamoDB error during get_video_url: %s", exc)
        return _error(500, "Failed to retrieve move")

    item = result.get("Item")
    if not item:
        return _not_found(f"Move '{move_id}' not found")

    video_key = item.get("videoKey", "").strip()
    if not video_key:
        return _not_found(f"No video associated with move '{move_id}'")

    s3 = _get_s3()
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": VIDEO_BUCKET, "Key": video_key},
            ExpiresIn=PRESIGNED_URL_EXPIRY,
        )
    except ClientError as exc:
        logger.error("S3 pre-sign error during get_video_url: %s", exc)
        return _error(500, "Failed to generate video URL")

    return _ok({"url": url, "expiresIn": PRESIGNED_URL_EXPIRY, "moveId": move_id})


def get_upload_url(event, context):
    """POST /videos/{moveId}/upload-url — generate a pre-signed PUT URL for uploading a video."""
    move_id = (event.get("pathParameters") or {}).get("moveId")
    if not move_id:
        return _bad_request("moveId path parameter is required")

    # Verify the move exists
    table = _get_moves_table()
    try:
        result = table.get_item(Key={"moveId": move_id})
    except ClientError as exc:
        logger.error("DynamoDB error during get_upload_url: %s", exc)
        return _error(500, "Failed to retrieve move")

    if not result.get("Item"):
        return _not_found(f"Move '{move_id}' not found")

    video_key = f"videos/{move_id}/{uuid.uuid4()}.mp4"

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
        logger.error("S3 pre-sign error during get_upload_url: %s", exc)
        return _error(500, "Failed to generate upload URL")

    return _ok(
        {
            "uploadUrl": upload_url,
            "videoKey": video_key,
            "expiresIn": PRESIGNED_URL_EXPIRY,
            "moveId": move_id,
        }
    )
