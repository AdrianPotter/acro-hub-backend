"""
Unit tests for lambdas/videos/handler.py
All S3 and DynamoDB calls are mocked — no real AWS credentials required.
"""
import importlib.util
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

_VIDEOS_PATH = os.path.join(os.path.dirname(__file__), "..", "lambdas", "videos", "handler.py")
_spec = importlib.util.spec_from_file_location("videos_handler", _VIDEOS_PATH)
videos_handler = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(videos_handler)


# ── Shared fixtures ───────────────────────────────────────────────────────────

SAMPLE_MOVE = {
    "moveId": "move-abc",
    "name": "Bird",
    "videoKey": "videos/move-abc/clip.mp4",
}

MOVE_WITHOUT_VIDEO = {
    "moveId": "move-novid",
    "name": "Unnamed",
    "videoKey": "",
}


def _move_id_event(move_id: str, groups: list[str] | None = None):
    event = {"pathParameters": {"moveId": move_id}}
    if groups is not None:
        event["requestContext"] = {
            "authorizer": {
                "claims": {
                    "cognito:groups": ",".join(groups),
                }
            }
        }
    return event


def _client_error(code: str):
    from botocore.exceptions import ClientError

    return ClientError({"Error": {"Code": code, "Message": "err"}}, "op")


# ── get_video_url ─────────────────────────────────────────────────────────────

class TestGetVideoUrl(unittest.TestCase):
    def setUp(self):
        videos_handler._s3 = None
        videos_handler._moves_table = None
        videos_handler._dynamodb = None

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_get_video_url_success(self, mock_boto_client, mock_boto_resource):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.generate_presigned_url.return_value = "https://s3.example.com/signed"

        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": SAMPLE_MOVE}

        resp = videos_handler.get_video_url(_move_id_event("move-abc"), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["url"], "https://s3.example.com/signed")
        self.assertEqual(body["moveId"], "move-abc")
        self.assertEqual(body["expiresIn"], 3600)

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_get_video_url_move_not_found(self, mock_boto_client, mock_boto_resource):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {}

        resp = videos_handler.get_video_url(_move_id_event("nonexistent"), None)

        self.assertEqual(resp["statusCode"], 404)
        body = json.loads(resp["body"])
        self.assertIn("not found", body["error"])

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_get_video_url_no_video_key(self, mock_boto_client, mock_boto_resource):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": MOVE_WITHOUT_VIDEO}

        resp = videos_handler.get_video_url(_move_id_event("move-novid"), None)

        self.assertEqual(resp["statusCode"], 404)
        body = json.loads(resp["body"])
        self.assertIn("No video", body["error"])

    def test_get_video_url_missing_move_id(self):
        resp = videos_handler.get_video_url({"pathParameters": None}, None)
        self.assertEqual(resp["statusCode"], 400)


# ── get_upload_url ────────────────────────────────────────────────────────────

class TestGetUploadUrl(unittest.TestCase):
    def setUp(self):
        videos_handler._s3 = None
        videos_handler._moves_table = None
        videos_handler._dynamodb = None

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_get_upload_url_success(self, mock_boto_client, mock_boto_resource):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.generate_presigned_url.return_value = "https://s3.example.com/upload-signed"

        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": SAMPLE_MOVE}

        resp = videos_handler.get_upload_url(_move_id_event("move-abc", groups=["contributors"]), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["uploadUrl"], "https://s3.example.com/upload-signed")
        self.assertIn("videoKey", body)
        self.assertTrue(body["videoKey"].startswith("videos/move-abc/"))
        self.assertTrue(body["videoKey"].endswith(".mp4"))
        self.assertEqual(body["expiresIn"], 3600)

        # Verify PUT was requested
        call_args = mock_s3.generate_presigned_url.call_args
        self.assertEqual(call_args[0][0], "put_object")

        # Verify videoKey was persisted to DynamoDB
        mock_table.update_item.assert_called_once()
        update_call = mock_table.update_item.call_args
        self.assertEqual(update_call.kwargs["Key"], {"moveId": "move-abc"})
        self.assertIn(":vk", update_call.kwargs["ExpressionAttributeValues"])
        persisted_key = update_call.kwargs["ExpressionAttributeValues"][":vk"]
        self.assertTrue(persisted_key.startswith("videos/move-abc/"))
        self.assertTrue(persisted_key.endswith(".mp4"))

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_get_upload_url_move_not_found(self, mock_boto_client, mock_boto_resource):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {}

        resp = videos_handler.get_upload_url(_move_id_event("missing", groups=["curators"]), None)

        self.assertEqual(resp["statusCode"], 404)

    def test_get_upload_url_missing_move_id(self):
        event = {"pathParameters": None, "requestContext": {"authorizer": {"claims": {"cognito:groups": "contributors"}}}}
        resp = videos_handler.get_upload_url(event, None)
        self.assertEqual(resp["statusCode"], 400)

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_get_upload_url_s3_error(self, mock_boto_client, mock_boto_resource):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": SAMPLE_MOVE}
        mock_s3.generate_presigned_url.side_effect = _client_error("AccessDenied")

        resp = videos_handler.get_upload_url(_move_id_event("move-abc", groups=["admins"]), None)

        self.assertEqual(resp["statusCode"], 500)

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_get_upload_url_dynamodb_update_error(self, mock_boto_client, mock_boto_resource):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.generate_presigned_url.return_value = "https://s3.example.com/upload-signed"

        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": SAMPLE_MOVE}
        mock_table.update_item.side_effect = _client_error("ValidationException")

        resp = videos_handler.get_upload_url(_move_id_event("move-abc", groups=["curators"]), None)

        self.assertEqual(resp["statusCode"], 500)
        body = json.loads(resp["body"])
        self.assertIn("persist", body["error"])

    def test_get_upload_url_forbidden_no_group(self):
        resp = videos_handler.get_upload_url(_move_id_event("move-abc", groups=[]), None)
        self.assertEqual(resp["statusCode"], 403)

    def test_get_upload_url_forbidden_wrong_group(self):
        resp = videos_handler.get_upload_url(_move_id_event("move-abc", groups=["viewers"]), None)
        self.assertEqual(resp["statusCode"], 403)

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_get_upload_url_allowed_contributor(self, mock_boto_client, mock_boto_resource):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.generate_presigned_url.return_value = "https://s3.example.com/upload-signed"
        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": SAMPLE_MOVE}
        resp = videos_handler.get_upload_url(_move_id_event("move-abc", groups=["contributors"]), None)
        self.assertEqual(resp["statusCode"], 200)

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_get_upload_url_allowed_curator(self, mock_boto_client, mock_boto_resource):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.generate_presigned_url.return_value = "https://s3.example.com/upload-signed"
        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": SAMPLE_MOVE}
        resp = videos_handler.get_upload_url(_move_id_event("move-abc", groups=["curators"]), None)
        self.assertEqual(resp["statusCode"], 200)

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_get_upload_url_allowed_admin(self, mock_boto_client, mock_boto_resource):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.generate_presigned_url.return_value = "https://s3.example.com/upload-signed"
        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": SAMPLE_MOVE}
        resp = videos_handler.get_upload_url(_move_id_event("move-abc", groups=["admins"]), None)
        self.assertEqual(resp["statusCode"], 200)


# ── Logging tests ─────────────────────────────────────────────────────────────

class TestVideosLogging(unittest.TestCase):
    """Verify that each handler emits the expected log messages."""

    def setUp(self):
        videos_handler._s3 = None
        videos_handler._moves_table = None
        videos_handler._dynamodb = None

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_get_video_url_logs_entry_and_response(self, mock_boto_client, mock_resource):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": SAMPLE_MOVE}
        mock_s3.generate_presigned_url.return_value = "https://presigned-url"

        with self.assertLogs("root", level="INFO") as cm:
            videos_handler.get_video_url(_move_id_event("move-abc"), None)

        messages = "\n".join(cm.output)
        self.assertIn("get_video_url called", messages)
        self.assertIn("move-abc", messages)
        self.assertIn("Returning status 200", messages)

    @patch("boto3.resource")
    def test_get_video_url_logs_not_found_warning(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {}

        with self.assertLogs("root", level="INFO") as cm:
            videos_handler.get_video_url(_move_id_event("ghost-id"), None)

        messages = "\n".join(cm.output)
        self.assertIn("ghost-id", messages)
        self.assertIn("not found", messages)
        self.assertIn("Returning status 404", messages)

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_get_upload_url_logs_entry_and_response(self, mock_boto_client, mock_resource):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": SAMPLE_MOVE}
        mock_s3.generate_presigned_url.return_value = "https://upload-url"

        with self.assertLogs("root", level="INFO") as cm:
            videos_handler.get_upload_url(_move_id_event("move-abc", groups=["contributors"]), None)

        messages = "\n".join(cm.output)
        self.assertIn("get_upload_url called", messages)
        self.assertIn("move-abc", messages)
        self.assertIn("Returning status 200", messages)


# ── CORS preflight ────────────────────────────────────────────────────────────

EXPECTED_ALLOW_METHODS = "OPTIONS,GET,POST,PUT,PATCH,DELETE"


class TestVideosCors(unittest.TestCase):
    """Verify CORS preflight responses include the correct headers."""

    def _options_event(self, path: str) -> dict:
        return {"path": path, "httpMethod": "OPTIONS", "pathParameters": {"moveId": "move-abc"}}

    def test_options_view_returns_200(self):
        resp = videos_handler.router(self._options_event("/videos/move-abc/view"), None)
        self.assertEqual(resp["statusCode"], 200)

    def test_options_view_allow_methods_superset(self):
        resp = videos_handler.router(self._options_event("/videos/move-abc/view"), None)
        allow_methods = resp["headers"].get("Access-Control-Allow-Methods", "")
        self.assertEqual(allow_methods, EXPECTED_ALLOW_METHODS)

    def test_options_view_allow_origin(self):
        resp = videos_handler.router(self._options_event("/videos/move-abc/view"), None)
        self.assertEqual(resp["headers"].get("Access-Control-Allow-Origin"), "*")

    def test_options_view_allow_headers(self):
        resp = videos_handler.router(self._options_event("/videos/move-abc/view"), None)
        self.assertEqual(resp["headers"].get("Access-Control-Allow-Headers"), "Content-Type,Authorization")

    def test_record_view_cors_headers_present(self):
        """Non-preflight responses also carry CORS headers so Lambda-proxy responses are valid."""
        with patch("boto3.resource") as mock_resource:
            mock_table = MagicMock()
            mock_resource.return_value.Table.return_value = mock_table
            mock_table.update_item.return_value = {"Attributes": {"moveId": "move-abc", "viewCount": 1}}
            videos_handler._moves_table = None
            videos_handler._dynamodb = None
            event = {"path": "/videos/move-abc/view", "httpMethod": "POST", "pathParameters": {"moveId": "move-abc"}}
            resp = videos_handler.record_view(event, None)
        self.assertEqual(resp["headers"].get("Access-Control-Allow-Methods"), EXPECTED_ALLOW_METHODS)


if __name__ == "__main__":
    unittest.main()


# ── get_view_count ────────────────────────────────────────────────────────────

class TestGetViewCount(unittest.TestCase):
    def setUp(self):
        videos_handler._moves_table = None
        videos_handler._dynamodb = None

    @patch("boto3.resource")
    def test_get_view_count_success(self, mock_resource):
        import decimal
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": {**SAMPLE_MOVE, "viewCount": decimal.Decimal("5")}}

        resp = videos_handler.get_view_count(_move_id_event("move-abc"), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["moveId"], "move-abc")
        self.assertEqual(body["viewCount"], 5)

    @patch("boto3.resource")
    def test_get_view_count_not_found(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {}

        resp = videos_handler.get_view_count(_move_id_event("missing"), None)

        self.assertEqual(resp["statusCode"], 404)

    def test_get_view_count_missing_move_id(self):
        resp = videos_handler.get_view_count({"pathParameters": None}, None)
        self.assertEqual(resp["statusCode"], 400)

    @patch("boto3.resource")
    def test_get_view_count_defaults_to_zero(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": SAMPLE_MOVE}

        resp = videos_handler.get_view_count(_move_id_event("move-abc"), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["viewCount"], 0)

    @patch("boto3.resource")
    def test_router_get_view_dispatches_to_get_view_count(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": {**SAMPLE_MOVE, "viewCount": 3}}

        event = {"path": "/videos/move-abc/view", "httpMethod": "GET", "pathParameters": {"moveId": "move-abc"}}
        resp = videos_handler.router(event, None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["viewCount"], 3)


# ── _DecimalEncoder (videos) ──────────────────────────────────────────────────

class TestVideosDecimalEncoder(unittest.TestCase):
    def test_integer_decimal_serialised_as_int(self):
        import decimal
        body = {"viewCount": decimal.Decimal("10")}
        result = json.loads(json.dumps(body, cls=videos_handler._DecimalEncoder))
        self.assertEqual(result["viewCount"], 10)
        self.assertIsInstance(result["viewCount"], int)
