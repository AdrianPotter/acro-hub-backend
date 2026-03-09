"""
Unit tests for lambdas/auth/handler.py
All Cognito calls are mocked — no real AWS credentials required.
"""
import importlib
import json
import sys
import unittest
from unittest.mock import MagicMock, patch

# ── Module loading helpers ─────────────────────────────────────────────────────
# Ensure the lambda source directory is importable as 'handler'
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambdas", "auth"))

import handler as auth_handler  # noqa: E402


# ── Shared fixtures ───────────────────────────────────────────────────────────

def _login_event(email="user@example.com", password="Password1!"):
    return {"body": json.dumps({"email": email, "password": password}), "headers": {}}


def _logout_event(token="valid-access-token"):
    return {"body": "{}", "headers": {"Authorization": f"Bearer {token}"}}


def _register_event(email="new@example.com", password="Password1!", name="Alice"):
    return {"body": json.dumps({"email": email, "password": password, "name": name})}


def _forgot_event(email="user@example.com"):
    return {"body": json.dumps({"email": email})}


def _confirm_event(email="user@example.com", code="123456", new_password="NewPass1!"):
    return {
        "body": json.dumps(
            {"email": email, "code": code, "newPassword": new_password}
        )
    }


def _client_error(code: str, message: str = "error"):
    from botocore.exceptions import ClientError

    return ClientError({"Error": {"Code": code, "Message": message}}, "operation")


# ── Login tests ───────────────────────────────────────────────────────────────

class TestLogin(unittest.TestCase):
    def setUp(self):
        auth_handler._cognito = None  # reset cached client

    @patch("boto3.client")
    def test_login_success(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.initiate_auth.return_value = {
            "AuthenticationResult": {
                "AccessToken": "access-tok",
                "IdToken": "id-tok",
                "RefreshToken": "refresh-tok",
                "ExpiresIn": 3600,
                "TokenType": "Bearer",
            }
        }

        resp = auth_handler.login(_login_event(), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["accessToken"], "access-tok")
        self.assertEqual(body["idToken"], "id-tok")
        mock_cognito.initiate_auth.assert_called_once()

    @patch("boto3.client")
    def test_login_user_not_found(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.initiate_auth.side_effect = _client_error("UserNotFoundException")

        resp = auth_handler.login(_login_event(), None)

        self.assertEqual(resp["statusCode"], 401)
        body = json.loads(resp["body"])
        self.assertIn("Invalid credentials", body["error"])

    @patch("boto3.client")
    def test_login_wrong_password(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.initiate_auth.side_effect = _client_error("NotAuthorizedException")

        resp = auth_handler.login(_login_event(password="wrong"), None)

        self.assertEqual(resp["statusCode"], 401)

    @patch("boto3.client")
    def test_login_unconfirmed_user(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.initiate_auth.side_effect = _client_error("UserNotConfirmedException")

        resp = auth_handler.login(_login_event(), None)

        self.assertEqual(resp["statusCode"], 403)

    def test_login_missing_fields(self):
        event = {"body": json.dumps({"email": "only@example.com"})}
        resp = auth_handler.login(event, None)
        self.assertEqual(resp["statusCode"], 400)

    def test_login_invalid_json(self):
        event = {"body": "not-json"}
        resp = auth_handler.login(event, None)
        self.assertEqual(resp["statusCode"], 400)


# ── Logout tests ──────────────────────────────────────────────────────────────

class TestLogout(unittest.TestCase):
    def setUp(self):
        auth_handler._cognito = None

    @patch("boto3.client")
    def test_logout_success(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.global_sign_out.return_value = {}

        resp = auth_handler.logout(_logout_event(), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertIn("Logged out", body["message"])
        mock_cognito.global_sign_out.assert_called_once_with(AccessToken="valid-access-token")

    @patch("boto3.client")
    def test_logout_invalid_token(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.global_sign_out.side_effect = _client_error("NotAuthorizedException")

        resp = auth_handler.logout(_logout_event("expired-token"), None)

        self.assertEqual(resp["statusCode"], 401)

    def test_logout_missing_token(self):
        event = {"body": "{}", "headers": {}}
        resp = auth_handler.logout(event, None)
        self.assertEqual(resp["statusCode"], 400)


# ── Register tests ────────────────────────────────────────────────────────────

class TestRegister(unittest.TestCase):
    def setUp(self):
        auth_handler._cognito = None

    @patch("boto3.client")
    def test_register_success(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.sign_up.return_value = {
            "UserSub": "abc-123",
            "UserConfirmed": False,
        }

        resp = auth_handler.register(_register_event(), None)

        self.assertEqual(resp["statusCode"], 201)
        body = json.loads(resp["body"])
        self.assertEqual(body["userSub"], "abc-123")
        self.assertFalse(body["confirmed"])

    @patch("boto3.client")
    def test_register_duplicate_email(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.sign_up.side_effect = _client_error("UsernameExistsException")

        resp = auth_handler.register(_register_event(), None)

        self.assertEqual(resp["statusCode"], 409)
        body = json.loads(resp["body"])
        self.assertIn("already exists", body["error"])

    @patch("boto3.client")
    def test_register_invalid_password(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.sign_up.side_effect = _client_error(
            "InvalidPasswordException", "Password too short"
        )

        resp = auth_handler.register(_register_event(password="weak"), None)

        self.assertEqual(resp["statusCode"], 400)

    def test_register_missing_fields(self):
        event = {"body": json.dumps({"email": "only@example.com"})}
        resp = auth_handler.register(event, None)
        self.assertEqual(resp["statusCode"], 400)


# ── Forgot password tests ─────────────────────────────────────────────────────

class TestForgotPassword(unittest.TestCase):
    def setUp(self):
        auth_handler._cognito = None

    @patch("boto3.client")
    def test_forgot_password_success(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.forgot_password.return_value = {}

        resp = auth_handler.forgot_password(_forgot_event(), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertIn("reset code", body["message"])

    @patch("boto3.client")
    def test_forgot_password_unknown_user_returns_200(self, mock_boto_client):
        """Should return 200 even for unknown users to prevent enumeration."""
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.forgot_password.side_effect = _client_error("UserNotFoundException")

        resp = auth_handler.forgot_password(_forgot_event(), None)

        self.assertEqual(resp["statusCode"], 200)

    def test_forgot_password_missing_email(self):
        event = {"body": "{}"}
        resp = auth_handler.forgot_password(event, None)
        self.assertEqual(resp["statusCode"], 400)


# ── Confirm password tests ────────────────────────────────────────────────────

class TestConfirmPassword(unittest.TestCase):
    def setUp(self):
        auth_handler._cognito = None

    @patch("boto3.client")
    def test_confirm_password_success(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.confirm_forgot_password.return_value = {}

        resp = auth_handler.confirm_password(_confirm_event(), None)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertIn("reset successfully", body["message"])

    @patch("boto3.client")
    def test_confirm_password_wrong_code(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.confirm_forgot_password.side_effect = _client_error(
            "CodeMismatchException"
        )

        resp = auth_handler.confirm_password(_confirm_event(code="000000"), None)

        self.assertEqual(resp["statusCode"], 400)
        body = json.loads(resp["body"])
        self.assertIn("Invalid", body["error"])

    @patch("boto3.client")
    def test_confirm_password_expired_code(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.confirm_forgot_password.side_effect = _client_error(
            "ExpiredCodeException"
        )

        resp = auth_handler.confirm_password(_confirm_event(), None)

        self.assertEqual(resp["statusCode"], 400)
        body = json.loads(resp["body"])
        self.assertIn("expired", body["error"])

    @patch("boto3.client")
    def test_confirm_password_user_not_found(self, mock_boto_client):
        mock_cognito = MagicMock()
        mock_boto_client.return_value = mock_cognito
        mock_cognito.confirm_forgot_password.side_effect = _client_error(
            "UserNotFoundException"
        )

        resp = auth_handler.confirm_password(_confirm_event(), None)

        self.assertEqual(resp["statusCode"], 404)

    def test_confirm_password_missing_fields(self):
        event = {"body": json.dumps({"email": "u@example.com"})}
        resp = auth_handler.confirm_password(event, None)
        self.assertEqual(resp["statusCode"], 400)


if __name__ == "__main__":
    unittest.main()
