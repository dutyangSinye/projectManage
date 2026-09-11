"""Feishu WebView bearer-token authentication regression tests."""

import os
import unittest
from unittest.mock import patch

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.main import (
    SessionUserMiddleware,
    issue_auth_token,
    session_user_id,
    verify_auth_token,
)


async def protected_test_app(scope, receive, send):
    """Expose the middleware user ID without starting the production application."""
    response = JSONResponse({"user_id": session_user_id.get()})
    await response(scope, receive, send)


class AuthTokenTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(
            os.environ,
            {
                "FEISHU_MODE": "app",
                "FEISHU_SESSION_SECRET": "test-session-secret-with-sufficient-entropy",
                "FEISHU_SESSION_MAX_AGE": "28800",
            },
            clear=False,
        )
        self.environment.start()
        self.client = TestClient(SessionUserMiddleware(protected_test_app))

    def tearDown(self):
        self.client.close()
        self.environment.stop()

    def test_signed_token_round_trip(self):
        token = issue_auth_token(42)
        self.assertEqual(verify_auth_token(token), 42)

    def test_valid_bearer_token_restores_current_user(self):
        token = issue_auth_token(42)
        response = self.client.get(
            "/api/v1/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["user_id"], 42)

    def test_valid_compatibility_header_restores_current_user(self):
        token = issue_auth_token(42)
        response = self.client.get(
            "/api/v1/protected",
            headers={"X-Xinye-Session": token},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["user_id"], 42)

    def test_valid_compatibility_header_falls_back_from_invalid_bearer(self):
        token = issue_auth_token(42)
        response = self.client.get(
            "/api/v1/protected",
            headers={
                "Authorization": "Bearer invalid-token",
                "X-Xinye-Session": token,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["user_id"], 42)

    def test_missing_or_invalid_token_is_rejected(self):
        missing = self.client.get("/api/v1/protected")
        invalid = self.client.get(
            "/api/v1/protected",
            headers={"Authorization": "Bearer invalid-token"},
        )
        self.assertEqual(missing.status_code, 401, missing.text)
        self.assertEqual(invalid.status_code, 401, invalid.text)


if __name__ == "__main__":
    unittest.main()
