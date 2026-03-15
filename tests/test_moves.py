"""
Unit tests for lambdas/moves/handler.py
All DynamoDB calls are mocked — no real AWS credentials required.
"""
import importlib.util
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

_MOVES_PATH = os.path.join(os.path.dirname(__file__), "..", "lambdas", "moves", "handler.py")
_spec = importlib.util.spec_from_file_location("moves_handler", _MOVES_PATH)
moves_handler = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(moves_handler)


# ── Shared fixtures ───────────────────────────────────────────────────────────

SAMPLE_MOVE = {
    "moveId": "move-123",
    "name": "Star",
    "description": "Classic star pose",
    "difficulty": "easy",
    "category": "acrobalance",
    "videoKey": "videos/move-123/abc.mp4",
    "tags": ["static", "beginner"],
    "createdAt": "2024-01-01T00:00:00+00:00",
    "updatedAt": "2024-01-01T00:00:00+00:00",
}


def _claims_context(groups: list[str] | None = None) -> dict:
    """Build a requestContext dict with Cognito claims for the given groups."""
    return {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "cognito:groups": ",".join(groups or []),
                }
            }
        }
    }


def _create_event(body: dict, groups: list[str] | None = None):
    event = {"body": json.dumps(body), "pathParameters": None}
    if groups is not None:
        event.update(_claims_context(groups))
    return event


def _id_event(move_id: str, body: dict | None = None, groups: list[str] | None = None):
    event = {
        "pathParameters": {"id": move_id},
        "body": json.dumps(body) if body else "{}",
    }
    if groups is not None:
        event.update(_claims_context(groups))
    return event


def _client_error(code: str, message: str = "error"):
    from botocore.exceptions import ClientError

    return ClientError({"Error": {"Code": code, "Message": message}}, "op")


# ── List moves ────────────────────────────────────────────────────────────────

class TestListMoves(unittest.TestCase):
    def setUp(self):
        moves_handler._table = None
        moves_handler._dynamodb = None

    @patch("boto3.resource")
    def test_list_moves_returns_items(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.scan.return_value = {"Items": [SAMPLE_MOVE]}

        resp = moves_handler.list_moves({}, None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(len(body["moves"]), 1)
        self.assertEqual(body["moves"][0]["name"], "Star")

    @patch("boto3.resource")
    def test_list_moves_empty(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.scan.return_value = {"Items": []}

        resp = moves_handler.list_moves({}, None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["count"], 0)

    @patch("boto3.resource")
    def test_list_moves_pagination(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        move_a = {**SAMPLE_MOVE, "moveId": "a"}
        move_b = {**SAMPLE_MOVE, "moveId": "b"}
        mock_table.scan.side_effect = [
            {"Items": [move_a], "LastEvaluatedKey": {"moveId": "a"}},
            {"Items": [move_b]},
        ]

        resp = moves_handler.list_moves({}, None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["count"], 2)


# ── Get move ──────────────────────────────────────────────────────────────────

class TestGetMove(unittest.TestCase):
    def setUp(self):
        moves_handler._table = None
        moves_handler._dynamodb = None

    @patch("boto3.resource")
    def test_get_move_success(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": SAMPLE_MOVE}

        resp = moves_handler.get_move(_id_event("move-123"), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["moveId"], "move-123")

    @patch("boto3.resource")
    def test_get_move_not_found(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {}

        resp = moves_handler.get_move(_id_event("nonexistent"), None)

        self.assertEqual(resp["statusCode"], 404)

    def test_get_move_missing_id(self):
        resp = moves_handler.get_move({"pathParameters": None}, None)
        self.assertEqual(resp["statusCode"], 400)


# ── Create move ───────────────────────────────────────────────────────────────

class TestCreateMove(unittest.TestCase):
    def setUp(self):
        moves_handler._table = None
        moves_handler._dynamodb = None

    @patch("boto3.resource")
    def test_create_move_success(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.put_item.return_value = {}

        payload = {
            "name": "Star",
            "description": "Classic star pose",
            "difficulty": "easy",
            "category": "acrobalance",
            "tags": ["beginner"],
        }
        resp = moves_handler.create_move(_create_event(payload, groups=["contributors"]), None)

        self.assertEqual(resp["statusCode"], 201)
        body = json.loads(resp["body"])
        self.assertEqual(body["name"], "Star")
        self.assertIn("moveId", body)
        mock_table.put_item.assert_called_once()

    def test_create_move_missing_name(self):
        resp = moves_handler.create_move(_create_event({"difficulty": "easy"}, groups=["curators"]), None)
        self.assertEqual(resp["statusCode"], 400)

    def test_create_move_invalid_difficulty(self):
        resp = moves_handler.create_move(
            _create_event({"name": "Test", "difficulty": "impossible"}, groups=["curators"]), None
        )
        self.assertEqual(resp["statusCode"], 400)

    def test_create_move_invalid_category(self):
        resp = moves_handler.create_move(
            _create_event({"name": "Test", "category": "ballet"}, groups=["admins"]), None
        )
        self.assertEqual(resp["statusCode"], 400)

    def test_create_move_invalid_json(self):
        event = {"body": "bad-json", "pathParameters": None}
        event.update(_claims_context(["contributors"]))
        resp = moves_handler.create_move(event, None)
        self.assertEqual(resp["statusCode"], 400)

    def test_create_move_forbidden_no_group(self):
        resp = moves_handler.create_move(_create_event({"name": "Star"}, groups=[]), None)
        self.assertEqual(resp["statusCode"], 403)

    def test_create_move_forbidden_wrong_group(self):
        resp = moves_handler.create_move(_create_event({"name": "Star"}, groups=["viewers"]), None)
        self.assertEqual(resp["statusCode"], 403)

    @patch("boto3.resource")
    def test_create_move_allowed_contributor(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.put_item.return_value = {}
        resp = moves_handler.create_move(_create_event({"name": "Star"}, groups=["contributors"]), None)
        self.assertEqual(resp["statusCode"], 201)

    @patch("boto3.resource")
    def test_create_move_allowed_curator(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.put_item.return_value = {}
        resp = moves_handler.create_move(_create_event({"name": "Star"}, groups=["curators"]), None)
        self.assertEqual(resp["statusCode"], 201)

    @patch("boto3.resource")
    def test_create_move_allowed_admin(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.put_item.return_value = {}
        resp = moves_handler.create_move(_create_event({"name": "Star"}, groups=["admins"]), None)
        self.assertEqual(resp["statusCode"], 201)


# ── Update move ───────────────────────────────────────────────────────────────

class TestUpdateMove(unittest.TestCase):
    def setUp(self):
        moves_handler._table = None
        moves_handler._dynamodb = None

    @patch("boto3.resource")
    def test_update_move_success(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        updated = {**SAMPLE_MOVE, "name": "Super Star"}
        mock_table.get_item.return_value = {"Item": SAMPLE_MOVE}
        mock_table.update_item.return_value = {"Attributes": updated}

        resp = moves_handler.update_move(_id_event("move-123", {"name": "Super Star"}, groups=["curators"]), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["name"], "Super Star")

    @patch("boto3.resource")
    def test_update_move_not_found(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {}

        resp = moves_handler.update_move(_id_event("missing", {"name": "X"}, groups=["admins"]), None)

        self.assertEqual(resp["statusCode"], 404)

    def test_update_move_missing_id(self):
        event = {"pathParameters": None, "body": "{}"}
        event.update(_claims_context(["curators"]))
        resp = moves_handler.update_move(event, None)
        self.assertEqual(resp["statusCode"], 400)

    def test_update_move_forbidden_no_group(self):
        resp = moves_handler.update_move(_id_event("move-123", {"name": "X"}, groups=[]), None)
        self.assertEqual(resp["statusCode"], 403)

    def test_update_move_forbidden_contributor(self):
        resp = moves_handler.update_move(_id_event("move-123", {"name": "X"}, groups=["contributors"]), None)
        self.assertEqual(resp["statusCode"], 403)

    @patch("boto3.resource")
    def test_update_move_allowed_curator(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": SAMPLE_MOVE}
        mock_table.update_item.return_value = {"Attributes": SAMPLE_MOVE}
        resp = moves_handler.update_move(_id_event("move-123", {"name": "X"}, groups=["curators"]), None)
        self.assertEqual(resp["statusCode"], 200)

    @patch("boto3.resource")
    def test_update_move_allowed_admin(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": SAMPLE_MOVE}
        mock_table.update_item.return_value = {"Attributes": SAMPLE_MOVE}
        resp = moves_handler.update_move(_id_event("move-123", {"name": "X"}, groups=["admins"]), None)
        self.assertEqual(resp["statusCode"], 200)


# ── Delete move ───────────────────────────────────────────────────────────────

class TestDeleteMove(unittest.TestCase):
    def setUp(self):
        moves_handler._table = None
        moves_handler._dynamodb = None

    @patch("boto3.resource")
    def test_delete_move_success(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": SAMPLE_MOVE}
        mock_table.delete_item.return_value = {}

        resp = moves_handler.delete_move(_id_event("move-123", groups=["curators"]), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertIn("deleted", body["message"])
        mock_table.delete_item.assert_called_once_with(Key={"moveId": "move-123"})

    @patch("boto3.resource")
    def test_delete_move_not_found(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {}

        resp = moves_handler.delete_move(_id_event("ghost", groups=["admins"]), None)

        self.assertEqual(resp["statusCode"], 404)

    def test_delete_move_missing_id(self):
        event = {"pathParameters": None}
        event.update(_claims_context(["curators"]))
        resp = moves_handler.delete_move(event, None)
        self.assertEqual(resp["statusCode"], 400)

    def test_delete_move_forbidden_no_group(self):
        resp = moves_handler.delete_move(_id_event("move-123", groups=[]), None)
        self.assertEqual(resp["statusCode"], 403)

    def test_delete_move_forbidden_contributor(self):
        resp = moves_handler.delete_move(_id_event("move-123", groups=["contributors"]), None)
        self.assertEqual(resp["statusCode"], 403)

    @patch("boto3.resource")
    def test_delete_move_allowed_curator(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": SAMPLE_MOVE}
        mock_table.delete_item.return_value = {}
        resp = moves_handler.delete_move(_id_event("move-123", groups=["curators"]), None)
        self.assertEqual(resp["statusCode"], 200)

    @patch("boto3.resource")
    def test_delete_move_allowed_admin(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": SAMPLE_MOVE}
        mock_table.delete_item.return_value = {}
        resp = moves_handler.delete_move(_id_event("move-123", groups=["admins"]), None)
        self.assertEqual(resp["statusCode"], 200)


# ── Logging tests ─────────────────────────────────────────────────────────────

class TestMovesLogging(unittest.TestCase):
    """Verify that each handler emits the expected log messages."""

    def setUp(self):
        moves_handler._table = None
        moves_handler._dynamodb = None

    @patch("boto3.resource")
    def test_list_moves_logs_entry_and_count(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.scan.return_value = {"Items": [SAMPLE_MOVE, SAMPLE_MOVE]}

        with self.assertLogs("root", level="INFO") as cm:
            moves_handler.list_moves({}, None)

        messages = "\n".join(cm.output)
        self.assertIn("list_moves called", messages)
        self.assertIn("2", messages)
        self.assertIn("Returning status 200", messages)

    @patch("boto3.resource")
    def test_get_move_logs_entry_and_not_found(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {}

        with self.assertLogs("root", level="INFO") as cm:
            moves_handler.get_move({"pathParameters": {"id": "ghost-id"}}, None)

        messages = "\n".join(cm.output)
        self.assertIn("ghost-id", messages)
        self.assertIn("not found", messages)
        self.assertIn("Returning status 404", messages)

    @patch("boto3.resource")
    def test_create_move_logs_name_difficulty_category(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.put_item.return_value = {}

        event = {"body": json.dumps({"name": "Throne", "difficulty": "hard", "category": "acrobalance"})}
        event.update(_claims_context(["contributors"]))

        with self.assertLogs("root", level="INFO") as cm:
            moves_handler.create_move(event, None)

        messages = "\n".join(cm.output)
        self.assertIn("Throne", messages)
        self.assertIn("hard", messages)
        self.assertIn("acrobalance", messages)
        self.assertIn("Returning status 201", messages)

    @patch("boto3.resource")
    def test_delete_move_logs_success(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": SAMPLE_MOVE}
        mock_table.delete_item.return_value = {}

        with self.assertLogs("root", level="INFO") as cm:
            moves_handler.delete_move(_id_event("move-123", groups=["curators"]), None)

        messages = "\n".join(cm.output)
        self.assertIn("delete_move called", messages)
        self.assertIn("move-123", messages)
        self.assertIn("Returning status 200", messages)


if __name__ == "__main__":
    unittest.main()
