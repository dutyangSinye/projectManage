import os
import unittest
from unittest.mock import patch

from nas_deploy_mcp.core import compose_command, Settings, runtime_image_command, tool_deploy, tool_rollback, wait_http_health


class CoreValidationTests(unittest.TestCase):
    def test_settings_requires_connection_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                Settings.from_env().validate()

    def test_deploy_defaults_to_preview(self):
        with patch.dict(os.environ, {"NAS_HOST": "nas", "NAS_USERNAME": "operator", "NAS_PASSWORD": "secret"}, clear=True):
            result = tool_deploy(False)
        self.assertTrue(result["requires_confirmation"])
        self.assertIn("pnpm build", result["plan"]["actions"])

    def test_rollback_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            tool_rollback("../../etc", False)

    def test_runtime_image_has_a_stable_default(self):
        with patch.dict(os.environ, {"NAS_HOST": "nas", "NAS_USERNAME": "operator", "NAS_PASSWORD": "secret"}, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.runtime_image, "xinye-project-management_runtime:20260905")
        command = runtime_image_command(settings)
        self.assertIn("docker image inspect", command)
        self.assertIn("Dockerfile.runtime", command)
        self.assertIn("[ ! -f", command)
        self.assertTrue(command.startswith("("))

    def test_compose_build_uses_runtime_image_argument(self):
        with patch.dict(os.environ, {"NAS_HOST": "nas", "NAS_USERNAME": "operator", "NAS_PASSWORD": "secret"}, clear=True):
            settings = Settings.from_env()
        command = compose_command(settings, "up")
        self.assertIn("--build", command)
        self.assertIn("docker-compose.yml", command)
        self.assertIn("docker ps -aq --filter name=xinye-workhours-api", command)
        self.assertIn("docker ps -aq --filter name=xinye-workhours-web", command)

    def test_health_wait_retries_transient_gateway_failure(self):
        with patch.dict(os.environ, {"NAS_HOST": "nas", "NAS_USERNAME": "operator", "NAS_PASSWORD": "secret"}, clear=True):
            settings = Settings.from_env()
        with patch("nas_deploy_mcp.core.http_health", side_effect=[{"ok": False, "status_code": 502}, {"ok": True, "status_code": 200}]) as health:
            result = wait_http_health(settings, attempts=3, interval_seconds=0)
        self.assertTrue(result["ok"])
        self.assertEqual(result["attempt"], 2)
        self.assertEqual(health.call_count, 2)


if __name__ == "__main__":
    unittest.main()
