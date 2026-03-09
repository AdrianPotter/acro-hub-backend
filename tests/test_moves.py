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


def _create_event(body: dict):
    return {"body": json.dumps(body), "pathParameters": None}


def _id_event(move_id: str, body: dict | None = None):
    return {
        "pathParameters": {"id": move_id},
        "body": json.dumps(body) if body else "{}",
    }


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
        resp = moves_handler.create_move(_create_event(payload), None)

        self.assertEqual(resp["statusCode"], 201)
        body = json.loads(resp["body"])
        self.assertEqual(body["name"], "Star")
        self.assertIn("moveId", body)
        mock_table.put_item.assert_called_once()

    def test_create_move_missing_name(self):
        resp = moves_handler.create_move(_create_event({"difficulty": "easy"}), None)
        self.assertEqual(resp["statusCode"], 400)

    def test_create_move_invalid_difficulty(self):
        resp = moves_handler.create_move(
            _create_event({"name": "Test", "difficulty": "impossible"}), None
        )
        self.assertEqual(resp["statusCode"], 400)

    def test_create_move_invalid_category(self):
        resp = moves_handler.create_move(
            _create_event({"name": "Test", "category": "ballet"}), None
        )
        self.assertEqual(resp["statusCode"], 400)

    def test_create_move_invalid_json(self):
        resp = moves_handler.create_move({"body": "bad-json", "pathParameters": None}, None)
        self.assertEqual(resp["statusCode"], 400)


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

        resp = moves_handler.update_move(_id_event("move-123", {"name": "Super Star"}), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["name"], "Super Star")

    @patch("boto3.resource")
    def test_update_move_not_found(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {}

        resp = moves_handler.update_move(_id_event("missing", {"name": "X"}), None)

        self.assertEqual(resp["statusCode"], 404)

    def test_update_move_missing_id(self):
        resp = moves_handler.update_move({"pathParameters": None, "body": "{}"}, None)
        self.assertEqual(resp["statusCode"], 400)


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

        resp = moves_handler.delete_move(_id_event("move-123"), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertIn("deleted", body["message"])
        mock_table.delete_item.assert_called_once_with(Key={"moveId": "move-123"})

    @patch("boto3.resource")
    def test_delete_move_not_found(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {}

        resp = moves_handler.delete_move(_id_event("ghost"), None)

        self.assertEqual(resp["statusCode"], 404)

    def test_delete_move_missing_id(self):
        resp = moves_handler.delete_move({"pathParameters": None}, None)
        self.assertEqual(resp["statusCode"], 400)


if __name__ == "__main__":
    unittest.main()
