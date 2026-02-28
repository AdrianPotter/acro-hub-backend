"""
Unit tests for lambdas/events/handler.py
All DynamoDB calls are mocked — no real AWS credentials required.
"""
import importlib.util
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

_EVENTS_PATH = os.path.join(os.path.dirname(__file__), "..", "lambdas", "events", "handler.py")
_spec = importlib.util.spec_from_file_location("events_handler", _EVENTS_PATH)
events_handler = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(events_handler)


# ── Shared fixtures ───────────────────────────────────────────────────────────

def _authed_event(body: dict | None = None, params: dict | None = None):
    """Simulate an API Gateway event with a Cognito authorizer context."""
    return {
        "body": json.dumps(body) if body else "{}",
        "queryStringParameters": params,
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "user-sub-abc123",
                    "email": "user@example.com",
                }
            }
        },
    }


def _client_error(code: str):
    from botocore.exceptions import ClientError

    return ClientError({"Error": {"Code": code, "Message": "err"}}, "op")


SAMPLE_EVENT = {
    "eventId": "evt-1",
    "eventType": "move_view",
    "userId": "user-sub-abc123",
    "resourceId": "move-123",
    "timestamp": "2024-06-01T10:00:00+00:00",
    "metadata": {},
}


# ── track_event ───────────────────────────────────────────────────────────────

class TestTrackEvent(unittest.TestCase):
    def setUp(self):
        events_handler._table = None
        events_handler._dynamodb = None

    @patch("boto3.resource")
    def test_track_event_success(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.put_item.return_value = {}

        event = _authed_event({"eventType": "move_view", "resourceId": "move-123"})
        resp = events_handler.track_event(event, None)

        self.assertEqual(resp["statusCode"], 201)
        body = json.loads(resp["body"])
        self.assertEqual(body["eventType"], "move_view")
        self.assertEqual(body["userId"], "user-sub-abc123")
        self.assertEqual(body["resourceId"], "move-123")
        self.assertIn("eventId", body)
        self.assertIn("timestamp", body)
        mock_table.put_item.assert_called_once()

    @patch("boto3.resource")
    def test_track_event_login(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.put_item.return_value = {}

        event = _authed_event({"eventType": "login"})
        resp = events_handler.track_event(event, None)

        self.assertEqual(resp["statusCode"], 201)

    def test_track_event_missing_event_type(self):
        event = _authed_event({})
        resp = events_handler.track_event(event, None)
        self.assertEqual(resp["statusCode"], 400)

    def test_track_event_invalid_event_type(self):
        event = _authed_event({"eventType": "hacked"})
        resp = events_handler.track_event(event, None)
        self.assertEqual(resp["statusCode"], 400)

    def test_track_event_invalid_json(self):
        event = {
            "body": "not-json",
            "requestContext": {"authorizer": {"claims": {"sub": "u1"}}},
        }
        resp = events_handler.track_event(event, None)
        self.assertEqual(resp["statusCode"], 400)

    @patch("boto3.resource")
    def test_track_event_with_metadata(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.put_item.return_value = {}

        event = _authed_event(
            {"eventType": "move_view", "resourceId": "m1", "metadata": {"source": "search"}}
        )
        resp = events_handler.track_event(event, None)

        self.assertEqual(resp["statusCode"], 201)
        body = json.loads(resp["body"])
        self.assertEqual(body["metadata"]["source"], "search")

    @patch("boto3.resource")
    def test_track_event_unknown_user(self, mock_resource):
        """If authorizer context is absent, userId should fall back to 'unknown'."""
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.put_item.return_value = {}

        event = {
            "body": json.dumps({"eventType": "login"}),
            "requestContext": {},
        }
        resp = events_handler.track_event(event, None)

        self.assertEqual(resp["statusCode"], 201)
        body = json.loads(resp["body"])
        self.assertEqual(body["userId"], "unknown")


# ── list_events ───────────────────────────────────────────────────────────────

class TestListEvents(unittest.TestCase):
    def setUp(self):
        events_handler._table = None
        events_handler._dynamodb = None

    @patch("boto3.resource")
    def test_list_events_no_filters(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.scan.return_value = {"Items": [SAMPLE_EVENT]}

        resp = events_handler.list_events(_authed_event(), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(len(body["events"]), 1)
        self.assertEqual(body["count"], 1)

    @patch("boto3.resource")
    def test_list_events_with_user_id_filter(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.query.return_value = {"Items": [SAMPLE_EVENT]}

        event = _authed_event(params={"userId": "user-sub-abc123"})
        resp = events_handler.list_events(event, None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["count"], 1)
        # Should use query (not scan) when userId is provided
        mock_table.query.assert_called_once()
        mock_table.scan.assert_not_called()

    @patch("boto3.resource")
    def test_list_events_with_event_type_filter(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.query.return_value = {"Items": [SAMPLE_EVENT]}

        event = _authed_event(params={"eventType": "move_view"})
        resp = events_handler.list_events(event, None)

        self.assertEqual(resp["statusCode"], 200)
        # Should use query (not scan) when eventType is provided
        mock_table.query.assert_called_once()
        mock_table.scan.assert_not_called()

    @patch("boto3.resource")
    def test_list_events_empty_result(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.scan.return_value = {"Items": []}

        resp = events_handler.list_events(_authed_event(), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["count"], 0)

    @patch("boto3.resource")
    def test_list_events_pagination(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        evt_a = {**SAMPLE_EVENT, "eventId": "a"}
        evt_b = {**SAMPLE_EVENT, "eventId": "b"}
        mock_table.scan.side_effect = [
            {"Items": [evt_a], "LastEvaluatedKey": {"eventId": "a"}},
            {"Items": [evt_b]},
        ]

        resp = events_handler.list_events(_authed_event(), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["count"], 2)

    @patch("boto3.resource")
    def test_list_events_with_date_range(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.scan.return_value = {"Items": [SAMPLE_EVENT]}

        event = _authed_event(
            params={
                "from": "2024-01-01T00:00:00+00:00",
                "to": "2024-12-31T23:59:59+00:00",
            }
        )
        resp = events_handler.list_events(event, None)

        self.assertEqual(resp["statusCode"], 200)
        # Should use scan with filter expression
        mock_table.scan.assert_called_once()


if __name__ == "__main__":
    unittest.main()
