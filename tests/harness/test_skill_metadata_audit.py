"""Offline checks that delivery evidence cannot pass vacuously."""

import json
import unittest

from test_skill_metadata import audit_messages, check_metadata, rendered_prompt


class EvidenceTests(unittest.TestCase):
    def test_claude_and_cursor_text_records(self):
        audit_messages([{"type": "assistant", "message": {
            "content": [{"type": "text", "text": "fixture metadata"}]}}])
        audit_messages([{"role": "assistant", "content": json.dumps([
            {"type": "text", "text": "fixture metadata"}])}])

    def test_tools_rejected_even_when_answer_is_correct(self):
        for part in ("tool_use", "tool-result", "tool-call", "tool-invocation", "function_call"):
            with self.subTest(part=part), self.assertRaises(RuntimeError):
                audit_messages([{"role": "assistant", "content": [
                    {"type": "text", "text": "correct metadata"}, {"type": part}]}])
        with self.assertRaises(RuntimeError):
            audit_messages([{"role": "tool", "content": "metadata"}])

    def test_missing_or_unknown_assistant_evidence_fails(self):
        for messages in ([], [{"role": "user", "content": "metadata"}],
                         [{"role": "assistant"}],
                         [{"role": "assistant", "content": [{"type": "future-format"}]}]):
            with self.subTest(messages=messages), self.assertRaises(RuntimeError):
                audit_messages(messages)

    def test_prompt_only_reads_message_content(self):
        raw = json.dumps([{"type": "message", "role": "developer",
                           "metadata": "not evidence", "content": [
                               {"type": "input_text", "text": "actual evidence"}]}])
        self.assertEqual(rendered_prompt(raw), "actual evidence")
        for raw in ("[]", "{}", "[{}]"):
            with self.subTest(raw=raw), self.assertRaises(RuntimeError):
                rendered_prompt(raw)

    def test_both_identifiers_required_and_body_excluded(self):
        check_metadata("name description", "name", "description", "BODY", True)
        check_metadata("NONE", "name", "description", "BODY", False)
        for output, installed in (("", False), ("name", True), ("description", True),
                                  ("name description BODY", True), ("name", False),
                                  ("description", False)):
            with self.subTest(output=output, installed=installed), self.assertRaises(RuntimeError):
                check_metadata(output, "name", "description", "BODY", installed)


if __name__ == "__main__":
    unittest.main()
