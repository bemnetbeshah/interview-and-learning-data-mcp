import json
import unittest
from pathlib import Path


class RailwayConfigTests(unittest.TestCase):
    def test_railway_config_pins_dockerfile_and_healthcheck(self):
        config = json.loads(Path("railway.json").read_text(encoding="utf-8"))

        self.assertEqual(config["$schema"], "https://railway.com/railway.schema.json")
        self.assertEqual(config["build"]["builder"], "DOCKERFILE")
        self.assertEqual(config["build"]["dockerfilePath"], "Dockerfile")
        self.assertEqual(config["deploy"]["healthcheckPath"], "/healthz")
        self.assertGreaterEqual(config["deploy"]["healthcheckTimeout"], 30)
        self.assertEqual(config["deploy"]["restartPolicyType"], "ON_FAILURE")
        self.assertGreaterEqual(config["deploy"]["restartPolicyMaxRetries"], 1)
