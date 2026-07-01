import unittest
from types import SimpleNamespace

from scripts.verify_authenticated_mcp import EXPECTED_PROMPTS, EXPECTED_TOOLS, validate_smoke_results


class VerifyAuthenticatedMcpTests(unittest.TestCase):
    def test_validate_smoke_results_accepts_expected_contract(self):
        init = SimpleNamespace(
            instructions="Call get_due_subtopics then log_attempt.",
            serverInfo=SimpleNamespace(websiteUrl="https://study.example.com"),
        )
        tools = [_tool(name) for name in EXPECTED_TOOLS]
        prompts = [SimpleNamespace(name=name) for name in EXPECTED_PROMPTS]
        prompt = SimpleNamespace(
            messages=[
                SimpleNamespace(
                    content=SimpleNamespace(text="Use get_due_subtopics first and log_attempt after each answer.")
                )
            ]
        )

        results = validate_smoke_results(init, tools, prompts, prompt)

        self.assertTrue(all(result.ok for result in results), results)

    def test_validate_smoke_results_rejects_missing_tool(self):
        init = SimpleNamespace(
            instructions="Call get_due_subtopics then log_attempt.",
            serverInfo=SimpleNamespace(websiteUrl="https://study.example.com"),
        )
        tools = [_tool(name) for name in EXPECTED_TOOLS if name != "delete_my_data"]
        prompts = [SimpleNamespace(name=name) for name in EXPECTED_PROMPTS]
        prompt = SimpleNamespace(
            messages=[
                SimpleNamespace(
                    content=SimpleNamespace(text="Use get_due_subtopics first and log_attempt after each answer.")
                )
            ]
        )

        results = validate_smoke_results(init, tools, prompts, prompt)

        self.assertFalse(next(result for result in results if result.name == "tools").ok)


def _tool(name):
    annotations = SimpleNamespace(destructiveHint=(name == "delete_my_data"))
    score_schema = {"minimum": 1, "maximum": 5}
    input_schema = {"properties": {"score": score_schema}} if name == "log_attempt" else {"properties": {}}
    return SimpleNamespace(name=name, annotations=annotations, inputSchema=input_schema)
