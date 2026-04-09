"""
Unit tests for lambdas/users/handler.py
All Cognito calls are mocked — no real AWS credentials required.
"""
import importlib.util
import json
import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

_USERS_PATH = os.path.join(os.path.dirname(__file__), "..", "lambdas", "users", "handler.py")
_spec = importlib.util.spec_from_file_location("users_handler", _USERS_PATH)
users_handler = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(users_handler)


# ── Shared fixtures ───────────────────────────────────────────────────────────

def _admin_event(body: dict | None = None, params: dict | None = None, path: str = "/users", method: str = "GET"):
    """Simulate an API Gateway event from an admin user."""
    return {
        "path": path,
        "httpMethod": method,
        "body": json.dumps(body) if body else None,
        "queryStringParameters": params,
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "admin-sub-abc123",
                    "email": "admin@example.com",
                    "cognito:groups": "admins curators",
                }
            }
        },
    }


def _non_admin_event(path: str = "/users", method: str = "GET"):
    """Simulate an API Gateway event from a non-admin user."""
    return {
        "path": path,
        "httpMethod": method,
        "body": None,
        "queryStringParameters": None,
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "user-sub-xyz",
                    "email": "user@example.com",
                    "cognito:groups": "contributors",
                }
            }
        },
    }


def _client_error(code: str, message: str = "error"):
    from botocore.exceptions import ClientError
    return ClientError({"Error": {"Code": code, "Message": message}}, "operation")


def _make_cognito_user(username="user@example.com", enabled=True, status="CONFIRMED", last_login=None):
    attrs = [
        {"Name": "email", "Value": username},
        {"Name": "name", "Value": "Test User"},
        {"Name": "sub", "Value": "sub-123"},
    ]
    if last_login is not None:
        attrs.append({"Name": "custom:last_login", "Value": last_login})
    return {
        "Username": username,
        "Attributes": attrs,
        "UserStatus": status,
        "Enabled": enabled,
        "UserCreateDate": datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
    }


# ── _require_admin ────────────────────────────────────────────────────────────

class TestRequireAdmin(unittest.TestCase):
    def test_admin_passes(self):
        event = _admin_event()
        result = users_handler._require_admin(event)
        self.assertIsNone(result)

    def test_non_admin_returns_403(self):
        event = _non_admin_event()
        result = users_handler._require_admin(event)
        self.assertIsNotNone(result)
        self.assertEqual(result["statusCode"], 403)

    def test_no_claims_returns_403(self):
        event = {"requestContext": {}}
        result = users_handler._require_admin(event)
        self.assertIsNotNone(result)
        self.assertEqual(result["statusCode"], 403)

    def test_groups_as_json_array(self):
        event = _admin_event()
        event["requestContext"]["authorizer"]["claims"]["cognito:groups"] = '["admins", "curators"]'
        result = users_handler._require_admin(event)
        self.assertIsNone(result)


# ── _format_user ──────────────────────────────────────────────────────────────

class TestFormatUser(unittest.TestCase):
    def test_last_login_absent_when_attribute_missing(self):
        user = _make_cognito_user("bob@example.com")
        result = users_handler._format_user(user, [])
        self.assertIsNone(result["lastLogin"])

    def test_last_login_present_when_attribute_set(self):
        user = _make_cognito_user("bob@example.com", last_login="2026-04-09T10:30:00Z")
        result = users_handler._format_user(user, [])
        self.assertEqual(result["lastLogin"], "2026-04-09T10:30:00Z")


# ── list_users ────────────────────────────────────────────────────────────────

class TestListUsers(unittest.TestCase):
    def setUp(self):
        users_handler._cognito = None

    @patch("boto3.client")
    def test_list_users_success(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.list_users.return_value = {
            "Users": [_make_cognito_user("alice@example.com")],
        }
        mock_cognito.admin_list_groups_for_user.return_value = {
            "Groups": [{"GroupName": "contributors"}]
        }

        event = _admin_event()
        resp = users_handler.list_users(event, None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["users"][0]["email"], "alice@example.com")
        self.assertEqual(body["users"][0]["groups"], ["contributors"])
        self.assertIsNone(body["users"][0]["lastLogin"])

    @patch("boto3.client")
    def test_list_users_last_login_populated(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.list_users.return_value = {
            "Users": [_make_cognito_user("alice@example.com", last_login="2026-04-09T12:00:00Z")],
        }
        mock_cognito.admin_list_groups_for_user.return_value = {"Groups": []}

        event = _admin_event()
        resp = users_handler.list_users(event, None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["users"][0]["lastLogin"], "2026-04-09T12:00:00Z")

    @patch("boto3.client")
    def test_list_users_pagination(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.list_users.side_effect = [
            {"Users": [_make_cognito_user("a@example.com")], "PaginationToken": "tok1"},
            {"Users": [_make_cognito_user("b@example.com")]},
        ]
        mock_cognito.admin_list_groups_for_user.return_value = {"Groups": []}

        event = _admin_event()
        resp = users_handler.list_users(event, None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["count"], 2)

    def test_list_users_non_admin_returns_403(self):
        event = _non_admin_event()
        resp = users_handler.list_users(event, None)
        self.assertEqual(resp["statusCode"], 403)

    @patch("boto3.client")
    def test_list_users_cognito_error(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.list_users.side_effect = _client_error("InternalErrorException")

        event = _admin_event()
        resp = users_handler.list_users(event, None)
        self.assertEqual(resp["statusCode"], 500)


# ── get_user ──────────────────────────────────────────────────────────────────

class TestGetUser(unittest.TestCase):
    def setUp(self):
        users_handler._cognito = None

    @patch("boto3.client")
    def test_get_user_success(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.admin_get_user.return_value = {
            "Username": "alice@example.com",
            "UserAttributes": [
                {"Name": "email", "Value": "alice@example.com"},
                {"Name": "name", "Value": "Alice"},
                {"Name": "sub", "Value": "sub-alice"},
            ],
            "UserStatus": "CONFIRMED",
            "Enabled": True,
            "UserCreateDate": datetime(2024, 3, 1, tzinfo=timezone.utc),
        }
        mock_cognito.admin_list_groups_for_user.return_value = {
            "Groups": [{"GroupName": "admins"}]
        }

        event = _admin_event(path="/users/alice@example.com", method="GET")
        resp = users_handler.get_user("alice@example.com", event, None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["email"], "alice@example.com")
        self.assertEqual(body["groups"], ["admins"])
        self.assertTrue(body["enabled"])

    @patch("boto3.client")
    def test_get_user_not_found(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.admin_get_user.side_effect = _client_error("UserNotFoundException")

        event = _admin_event(path="/users/nobody@example.com", method="GET")
        resp = users_handler.get_user("nobody@example.com", event, None)
        self.assertEqual(resp["statusCode"], 404)

    def test_get_user_non_admin_returns_403(self):
        event = _non_admin_event(path="/users/alice@example.com", method="GET")
        resp = users_handler.get_user("alice@example.com", event, None)
        self.assertEqual(resp["statusCode"], 403)


# ── update_user_groups ────────────────────────────────────────────────────────

class TestUpdateUserGroups(unittest.TestCase):
    def setUp(self):
        users_handler._cognito = None

    @patch("boto3.client")
    def test_update_groups_add_and_remove(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.admin_get_user.return_value = {"Username": "u@example.com"}
        mock_cognito.admin_list_groups_for_user.return_value = {
            "Groups": [{"GroupName": "contributors"}]
        }

        event = _admin_event(body={"groups": ["curators"]}, path="/users/u@example.com/groups", method="PUT")
        resp = users_handler.update_user_groups("u@example.com", event, None)

        self.assertEqual(resp["statusCode"], 200)
        # contributors should be removed, curators added
        mock_cognito.admin_add_user_to_group.assert_called_once_with(
            UserPoolId=users_handler.COGNITO_USER_POOL_ID,
            Username="u@example.com",
            GroupName="curators",
        )
        mock_cognito.admin_remove_user_from_group.assert_called_once_with(
            UserPoolId=users_handler.COGNITO_USER_POOL_ID,
            Username="u@example.com",
            GroupName="contributors",
        )

    @patch("boto3.client")
    def test_update_groups_no_change(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.admin_get_user.return_value = {"Username": "u@example.com"}
        mock_cognito.admin_list_groups_for_user.return_value = {
            "Groups": [{"GroupName": "contributors"}]
        }

        event = _admin_event(body={"groups": ["contributors"]}, path="/users/u@example.com/groups", method="PUT")
        resp = users_handler.update_user_groups("u@example.com", event, None)

        self.assertEqual(resp["statusCode"], 200)
        mock_cognito.admin_add_user_to_group.assert_not_called()
        mock_cognito.admin_remove_user_from_group.assert_not_called()

    def test_update_groups_missing_field(self):
        event = _admin_event(body={}, path="/users/u@example.com/groups", method="PUT")
        resp = users_handler.update_user_groups("u@example.com", event, None)
        self.assertEqual(resp["statusCode"], 400)
        self.assertIn("groups is required", json.loads(resp["body"])["error"])

    def test_update_groups_not_a_list(self):
        event = _admin_event(body={"groups": "admins"}, path="/users/u@example.com/groups", method="PUT")
        resp = users_handler.update_user_groups("u@example.com", event, None)
        self.assertEqual(resp["statusCode"], 400)

    def test_update_groups_invalid_group(self):
        event = _admin_event(body={"groups": ["superadmin"]}, path="/users/u@example.com/groups", method="PUT")
        resp = users_handler.update_user_groups("u@example.com", event, None)
        self.assertEqual(resp["statusCode"], 400)
        self.assertIn("Invalid group", json.loads(resp["body"])["error"])

    def test_update_groups_non_admin_returns_403(self):
        event = _non_admin_event(path="/users/u@example.com/groups", method="PUT")
        event["body"] = json.dumps({"groups": ["contributors"]})
        resp = users_handler.update_user_groups("u@example.com", event, None)
        self.assertEqual(resp["statusCode"], 403)

    @patch("boto3.client")
    def test_update_groups_user_not_found(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.admin_get_user.side_effect = _client_error("UserNotFoundException")

        event = _admin_event(body={"groups": ["admins"]}, path="/users/nobody@example.com/groups", method="PUT")
        resp = users_handler.update_user_groups("nobody@example.com", event, None)
        self.assertEqual(resp["statusCode"], 404)

    def test_update_groups_invalid_json_body(self):
        event = _admin_event(path="/users/u@example.com/groups", method="PUT")
        event["body"] = "not-json"
        resp = users_handler.update_user_groups("u@example.com", event, None)
        self.assertEqual(resp["statusCode"], 400)


# ── disable_user ──────────────────────────────────────────────────────────────

class TestDisableUser(unittest.TestCase):
    def setUp(self):
        users_handler._cognito = None

    @patch("boto3.client")
    def test_disable_user_success(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.admin_disable_user.return_value = {}

        event = _admin_event(path="/users/u@example.com/disable", method="POST")
        resp = users_handler.disable_user("u@example.com", event, None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertIn("disabled", body["message"])
        mock_cognito.admin_disable_user.assert_called_once_with(
            UserPoolId=users_handler.COGNITO_USER_POOL_ID,
            Username="u@example.com",
        )

    @patch("boto3.client")
    def test_disable_user_not_found(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.admin_disable_user.side_effect = _client_error("UserNotFoundException")

        event = _admin_event(path="/users/nobody@example.com/disable", method="POST")
        resp = users_handler.disable_user("nobody@example.com", event, None)
        self.assertEqual(resp["statusCode"], 404)

    def test_disable_user_non_admin_returns_403(self):
        event = _non_admin_event(path="/users/u@example.com/disable", method="POST")
        resp = users_handler.disable_user("u@example.com", event, None)
        self.assertEqual(resp["statusCode"], 403)

    @patch("boto3.client")
    def test_disable_user_cognito_error(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.admin_disable_user.side_effect = _client_error("InternalErrorException")

        event = _admin_event(path="/users/u@example.com/disable", method="POST")
        resp = users_handler.disable_user("u@example.com", event, None)
        self.assertEqual(resp["statusCode"], 500)


# ── enable_user ───────────────────────────────────────────────────────────────

class TestEnableUser(unittest.TestCase):
    def setUp(self):
        users_handler._cognito = None

    @patch("boto3.client")
    def test_enable_user_success(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.admin_enable_user.return_value = {}

        event = _admin_event(path="/users/u@example.com/enable", method="POST")
        resp = users_handler.enable_user("u@example.com", event, None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertIn("enabled", body["message"])
        mock_cognito.admin_enable_user.assert_called_once_with(
            UserPoolId=users_handler.COGNITO_USER_POOL_ID,
            Username="u@example.com",
        )

    @patch("boto3.client")
    def test_enable_user_not_found(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.admin_enable_user.side_effect = _client_error("UserNotFoundException")

        event = _admin_event(path="/users/nobody@example.com/enable", method="POST")
        resp = users_handler.enable_user("nobody@example.com", event, None)
        self.assertEqual(resp["statusCode"], 404)

    def test_enable_user_non_admin_returns_403(self):
        event = _non_admin_event(path="/users/u@example.com/enable", method="POST")
        resp = users_handler.enable_user("u@example.com", event, None)
        self.assertEqual(resp["statusCode"], 403)


# ── delete_user ───────────────────────────────────────────────────────────────

class TestDeleteUser(unittest.TestCase):
    def setUp(self):
        users_handler._cognito = None

    @patch("boto3.client")
    def test_delete_user_success(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.admin_delete_user.return_value = {}

        event = _admin_event(path="/users/u@example.com", method="DELETE")
        resp = users_handler.delete_user("u@example.com", event, None)

        self.assertEqual(resp["statusCode"], 204)
        mock_cognito.admin_delete_user.assert_called_once_with(
            UserPoolId=users_handler.COGNITO_USER_POOL_ID,
            Username="u@example.com",
        )

    @patch("boto3.client")
    def test_delete_user_not_found(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.admin_delete_user.side_effect = _client_error("UserNotFoundException")

        event = _admin_event(path="/users/nobody@example.com", method="DELETE")
        resp = users_handler.delete_user("nobody@example.com", event, None)
        self.assertEqual(resp["statusCode"], 404)

    def test_delete_user_non_admin_returns_403(self):
        event = _non_admin_event(path="/users/u@example.com", method="DELETE")
        resp = users_handler.delete_user("u@example.com", event, None)
        self.assertEqual(resp["statusCode"], 403)

    @patch("boto3.client")
    def test_delete_user_cognito_error(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.admin_delete_user.side_effect = _client_error("InternalErrorException")

        event = _admin_event(path="/users/u@example.com", method="DELETE")
        resp = users_handler.delete_user("u@example.com", event, None)
        self.assertEqual(resp["statusCode"], 500)


# ── router ────────────────────────────────────────────────────────────────────

class TestRouter(unittest.TestCase):
    def setUp(self):
        users_handler._cognito = None

    def test_options_returns_200(self):
        event = {"path": "/users", "httpMethod": "OPTIONS", "requestContext": {}}
        resp = users_handler.router(event, None)
        self.assertEqual(resp["statusCode"], 200)

    def test_unknown_path_returns_404(self):
        event = _admin_event(path="/users/foo/bar/baz", method="GET")
        resp = users_handler.router(event, None)
        self.assertEqual(resp["statusCode"], 404)

    @patch("boto3.client")
    def test_router_get_users(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.list_users.return_value = {"Users": []}

        event = _admin_event(path="/users", method="GET")
        resp = users_handler.router(event, None)
        self.assertEqual(resp["statusCode"], 200)

    @patch("boto3.client")
    def test_router_get_user(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.admin_get_user.return_value = {
            "Username": "u@example.com",
            "UserAttributes": [],
            "UserStatus": "CONFIRMED",
            "Enabled": True,
            "UserCreateDate": datetime(2024, 1, 1, tzinfo=timezone.utc),
        }
        mock_cognito.admin_list_groups_for_user.return_value = {"Groups": []}

        event = _admin_event(path="/users/u@example.com", method="GET")
        resp = users_handler.router(event, None)
        self.assertEqual(resp["statusCode"], 200)

    @patch("boto3.client")
    def test_router_delete_user(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.admin_delete_user.return_value = {}

        event = _admin_event(path="/users/u@example.com", method="DELETE")
        resp = users_handler.router(event, None)
        self.assertEqual(resp["statusCode"], 204)

    @patch("boto3.client")
    def test_router_put_groups(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.admin_get_user.return_value = {"Username": "u@example.com"}
        mock_cognito.admin_list_groups_for_user.return_value = {"Groups": []}

        event = _admin_event(body={"groups": ["admins"]}, path="/users/u@example.com/groups", method="PUT")
        resp = users_handler.router(event, None)
        self.assertEqual(resp["statusCode"], 200)

    @patch("boto3.client")
    def test_router_disable_user(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.admin_disable_user.return_value = {}

        event = _admin_event(path="/users/u@example.com/disable", method="POST")
        resp = users_handler.router(event, None)
        self.assertEqual(resp["statusCode"], 200)

    @patch("boto3.client")
    def test_router_enable_user(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.admin_enable_user.return_value = {}

        event = _admin_event(path="/users/u@example.com/enable", method="POST")
        resp = users_handler.router(event, None)
        self.assertEqual(resp["statusCode"], 200)


if __name__ == "__main__":
    unittest.main()
