"""Offline checks for skill-body delivery evidence."""

import unittest

from test_skill_body import body_evidence


class BodyEvidenceTests(unittest.TestCase):
    def check(self, records, present=True, output="BODY-secret"):
        return body_evidence(records, "probe-name", "BODY-secret", present, output)

    def test_claude_skill_expansion(self):
        self.check([{"type": "user", "message": {"role": "user", "content":
                    "Skill contents: Body-only marker: BODY-secret"}}])

    def test_codex_read_result(self):
        self.check([{"type": "response_item", "payload": {
            "type": "function_call_output", "output": "Body-only marker: BODY-secret"}}])
        self.check([{"type": "response_item", "payload": {
            "type": "custom_tool_call_output", "output": [
                {"type": "input_text", "text": "Body-only marker: BODY-secret"}]}}])

    def test_cursor_tool_result(self):
        self.check([{"role": "assistant", "content": [
            {"type": "tool-result", "result": "Body-only marker: BODY-secret"}]}])

    def test_assistant_echo_or_call_arguments_do_not_prove_delivery(self):
        for part in ("text", "tool-call", "tool-invocation"):
            with self.subTest(part=part), self.assertRaises(RuntimeError):
                self.check([{"role": "assistant", "content": [
                    {"type": part, "text": "Body-only marker: BODY-secret"}]}])

    def test_control_must_load_body(self):
        self.check([{"role": "tool", "content": "No body marker is supplied."}],
                   present=False, output="NONE")
        for content in ("Skill unavailable", "Body-only marker: BODY-secret"):
            with self.subTest(content=content), self.assertRaises(RuntimeError):
                self.check([{"role": "tool", "content": content}], present=False, output="NONE")

    def test_missing_response_or_incoming_evidence_fails(self):
        for records, output in (([], "BODY-secret"),
                                ([{"role": "tool", "content": "Body-only marker: BODY-secret"}], "NONE"),
                                ([{"role": "tool", "content": "Body-only marker: BODY-secret"}], "")):
            with self.subTest(output=output), self.assertRaises(RuntimeError):
                self.check(records, output=output)


if __name__ == "__main__":
    unittest.main()
