"""
Unit tests for lambdas/user-move-lists/handler.py
All DynamoDB calls are mocked — no real AWS credentials required.
"""
import importlib.util
import json
import os
import unittest
from unittest.mock import MagicMock, patch

_HANDLER_PATH = os.path.join(
    os.path.dirname(__file__), "..", "lambdas", "user-move-lists", "handler.py"
)
_spec = importlib.util.spec_from_file_location("user_move_lists_handler", _HANDLER_PATH)
handler = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(handler)


# ── Shared fixtures ───────────────────────────────────────────────────────────

USER_ID = "user-sub-abc123"
MOVE_ID = "move-456"


def _authed_event(path: str, method: str) -> dict:
    """Build an API Gateway event with a Cognito sub claim."""
    return {
        "path": path,
        "httpMethod": method,
        "body": "{}",
        "pathParameters": None,
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": USER_ID,
                }
            }
        },
    }


def _unauthed_event(path: str, method: str) -> dict:
    """Build an API Gateway event with no authorizer context."""
    return {
        "path": path,
        "httpMethod": method,
        "body": "{}",
        "pathParameters": None,
        "requestContext": {},
    }


def _client_error(code: str):
    from botocore.exceptions import ClientError
    return ClientError({"Error": {"Code": code, "Message": "err"}}, "op")


# ── List moves in list ────────────────────────────────────────────────────────

class TestListMovesInList(unittest.TestCase):
    def setUp(self):
        handler._table = None
        handler._dynamodb = None

    @patch("boto3.resource")
    def test_list_favourites_returns_move_ids(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.query.return_value = {
            "Items": [
                {"userId": USER_ID, "listType#moveId": "favourites#move-1", "listType": "favourites", "moveId": "move-1"},
                {"userId": USER_ID, "listType#moveId": "favourites#move-2", "listType": "favourites", "moveId": "move-2"},
            ]
        }

        resp = handler.list_moves_in_list("favourites", _authed_event("/me/moves/favourites", "GET"), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["listType"], "favourites")
        self.assertIn("move-1", body["moveIds"])
        self.assertIn("move-2", body["moveIds"])
        self.assertEqual(body["count"], 2)

    @patch("boto3.resource")
    def test_list_returns_empty_when_no_moves(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.query.return_value = {"Items": []}

        resp = handler.list_moves_in_list("learned", _authed_event("/me/moves/learned", "GET"), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["count"], 0)
        self.assertEqual(body["moveIds"], [])

    @patch("boto3.resource")
    def test_list_handles_pagination(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        item_a = {"userId": USER_ID, "listType#moveId": "favourites#move-a", "listType": "favourites", "moveId": "move-a"}
        item_b = {"userId": USER_ID, "listType#moveId": "favourites#move-b", "listType": "favourites", "moveId": "move-b"}
        mock_table.query.side_effect = [
            {"Items": [item_a], "LastEvaluatedKey": {"userId": USER_ID, "listType#moveId": "favourites#move-a"}},
            {"Items": [item_b]},
        ]

        resp = handler.list_moves_in_list("favourites", _authed_event("/me/moves/favourites", "GET"), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["count"], 2)

    def test_list_returns_401_when_not_authed(self):
        resp = handler.list_moves_in_list("favourites", _unauthed_event("/me/moves/favourites", "GET"), None)
        self.assertEqual(resp["statusCode"], 401)

    @patch("boto3.resource")
    def test_list_returns_500_on_dynamodb_error(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.query.side_effect = _client_error("InternalServerError")

        resp = handler.list_moves_in_list("favourites", _authed_event("/me/moves/favourites", "GET"), None)

        self.assertEqual(resp["statusCode"], 500)


# ── Add move to list ──────────────────────────────────────────────────────────

class TestAddMoveToList(unittest.TestCase):
    def setUp(self):
        handler._table = None
        handler._dynamodb = None

    @patch("boto3.resource")
    def test_add_move_success(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.put_item.return_value = {}

        resp = handler.add_move_to_list("favourites", MOVE_ID, _authed_event("/me/moves/favourites/" + MOVE_ID, "PUT"), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["listType"], "favourites")
        self.assertEqual(body["moveId"], MOVE_ID)
        mock_table.put_item.assert_called_once_with(Item={
            "userId": USER_ID,
            "listType#moveId": f"favourites#{MOVE_ID}",
            "listType": "favourites",
            "moveId": MOVE_ID,
        })

    @patch("boto3.resource")
    def test_add_move_to_learned(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.put_item.return_value = {}

        resp = handler.add_move_to_list("learned", MOVE_ID, _authed_event("/me/moves/learned/" + MOVE_ID, "PUT"), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["listType"], "learned")

    @patch("boto3.resource")
    def test_add_move_to_want_to_learn(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.put_item.return_value = {}

        resp = handler.add_move_to_list("want-to-learn", MOVE_ID, _authed_event("/me/moves/want-to-learn/" + MOVE_ID, "PUT"), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["listType"], "want-to-learn")

    def test_add_move_returns_401_when_not_authed(self):
        resp = handler.add_move_to_list("favourites", MOVE_ID, _unauthed_event("/me/moves/favourites/" + MOVE_ID, "PUT"), None)
        self.assertEqual(resp["statusCode"], 401)

    @patch("boto3.resource")
    def test_add_move_returns_500_on_dynamodb_error(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.put_item.side_effect = _client_error("InternalServerError")

        resp = handler.add_move_to_list("favourites", MOVE_ID, _authed_event("/me/moves/favourites/" + MOVE_ID, "PUT"), None)

        self.assertEqual(resp["statusCode"], 500)


# ── Remove move from list ─────────────────────────────────────────────────────

class TestRemoveMoveFromList(unittest.TestCase):
    def setUp(self):
        handler._table = None
        handler._dynamodb = None

    @patch("boto3.resource")
    def test_remove_move_success(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.delete_item.return_value = {}

        resp = handler.remove_move_from_list("favourites", MOVE_ID, _authed_event("/me/moves/favourites/" + MOVE_ID, "DELETE"), None)

        self.assertEqual(resp["statusCode"], 204)
        mock_table.delete_item.assert_called_once_with(
            Key={"userId": USER_ID, "listType#moveId": f"favourites#{MOVE_ID}"}
        )

    @patch("boto3.resource")
    def test_remove_move_from_learned(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.delete_item.return_value = {}

        resp = handler.remove_move_from_list("learned", MOVE_ID, _authed_event("/me/moves/learned/" + MOVE_ID, "DELETE"), None)

        self.assertEqual(resp["statusCode"], 204)

    def test_remove_move_returns_401_when_not_authed(self):
        resp = handler.remove_move_from_list("favourites", MOVE_ID, _unauthed_event("/me/moves/favourites/" + MOVE_ID, "DELETE"), None)
        self.assertEqual(resp["statusCode"], 401)

    @patch("boto3.resource")
    def test_remove_move_returns_500_on_dynamodb_error(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.delete_item.side_effect = _client_error("InternalServerError")

        resp = handler.remove_move_from_list("favourites", MOVE_ID, _authed_event("/me/moves/favourites/" + MOVE_ID, "DELETE"), None)

        self.assertEqual(resp["statusCode"], 500)


# ── Router ────────────────────────────────────────────────────────────────────

class TestRouter(unittest.TestCase):
    def setUp(self):
        handler._table = None
        handler._dynamodb = None

    def test_options_returns_200(self):
        event = _authed_event("/me/moves/favourites", "OPTIONS")
        resp = handler.router(event, None)
        self.assertEqual(resp["statusCode"], 200)

    @patch("boto3.resource")
    def test_routes_get_list(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.query.return_value = {"Items": []}

        resp = handler.router(_authed_event("/me/moves/favourites", "GET"), None)
        self.assertEqual(resp["statusCode"], 200)

    @patch("boto3.resource")
    def test_routes_put_move(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.put_item.return_value = {}

        resp = handler.router(_authed_event(f"/me/moves/learned/{MOVE_ID}", "PUT"), None)
        self.assertEqual(resp["statusCode"], 200)

    @patch("boto3.resource")
    def test_routes_delete_move(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.delete_item.return_value = {}

        resp = handler.router(_authed_event(f"/me/moves/want-to-learn/{MOVE_ID}", "DELETE"), None)
        self.assertEqual(resp["statusCode"], 204)

    def test_invalid_list_type_on_get_returns_400(self):
        resp = handler.router(_authed_event("/me/moves/invalid-list", "GET"), None)
        self.assertEqual(resp["statusCode"], 400)

    def test_invalid_list_type_on_put_returns_400(self):
        resp = handler.router(_authed_event(f"/me/moves/bad-list/{MOVE_ID}", "PUT"), None)
        self.assertEqual(resp["statusCode"], 400)

    def test_invalid_list_type_on_delete_returns_400(self):
        resp = handler.router(_authed_event(f"/me/moves/bad-list/{MOVE_ID}", "DELETE"), None)
        self.assertEqual(resp["statusCode"], 400)

    def test_unknown_path_returns_404(self):
        resp = handler.router(_authed_event("/me/other", "GET"), None)
        self.assertEqual(resp["statusCode"], 404)

    def test_post_on_move_path_returns_404(self):
        resp = handler.router(_authed_event(f"/me/moves/favourites/{MOVE_ID}", "POST"), None)
        self.assertEqual(resp["statusCode"], 404)


# ── Logging ───────────────────────────────────────────────────────────────────

class TestLogging(unittest.TestCase):
    def setUp(self):
        handler._table = None
        handler._dynamodb = None

    @patch("boto3.resource")
    def test_list_moves_logs_entry_and_count(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        item = {"userId": USER_ID, "listType#moveId": "favourites#m1", "listType": "favourites", "moveId": "m1"}
        mock_table.query.return_value = {"Items": [item]}

        with self.assertLogs("root", level="INFO") as cm:
            handler.list_moves_in_list("favourites", _authed_event("/me/moves/favourites", "GET"), None)

        messages = "\n".join(cm.output)
        self.assertIn("list_moves_in_list", messages)
        self.assertIn("favourites", messages)
        self.assertIn("Returning status 200", messages)

    @patch("boto3.resource")
    def test_add_move_logs_entry_and_success(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.put_item.return_value = {}

        with self.assertLogs("root", level="INFO") as cm:
            handler.add_move_to_list("learned", MOVE_ID, _authed_event(f"/me/moves/learned/{MOVE_ID}", "PUT"), None)

        messages = "\n".join(cm.output)
        self.assertIn("add_move_to_list", messages)
        self.assertIn(MOVE_ID, messages)
        self.assertIn("Returning status 200", messages)

    @patch("boto3.resource")
    def test_remove_move_logs_entry_and_success(self, mock_resource):
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        mock_table.delete_item.return_value = {}

        with self.assertLogs("root", level="INFO") as cm:
            handler.remove_move_from_list("favourites", MOVE_ID, _authed_event(f"/me/moves/favourites/{MOVE_ID}", "DELETE"), None)

        messages = "\n".join(cm.output)
        self.assertIn("remove_move_from_list", messages)
        self.assertIn(MOVE_ID, messages)
        self.assertIn("Returning status 204", messages)


if __name__ == "__main__":
    unittest.main()
