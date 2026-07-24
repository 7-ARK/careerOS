"""Focused tests for autonomous scope, branch, redaction, and loop policy."""

import unittest

from app.autonomy.policy import (
    BoundedExecutionPolicy,
    FailureClass,
    PolicyViolation,
    TaskScope,
    is_prohibited_path,
    normalize_relative_path,
    validate_branch,
)
from app.autonomy.redaction import redact_mapping, redact_text


class PolicyTests(unittest.TestCase):
    """Verify deterministic safety invariants without provider calls."""

    def test_non_main_branch_and_relative_paths_are_required(self) -> None:
        self.assertEqual(validate_branch("autonomy/task-1"), "autonomy/task-1")
        with self.assertRaises(PolicyViolation):
            validate_branch("main")
        with self.assertRaises(PolicyViolation):
            normalize_relative_path("../outside.txt")
        with self.assertRaises(PolicyViolation):
            normalize_relative_path("C:/outside.txt")

    def test_scope_and_secret_paths_are_enforced(self) -> None:
        scope = TaskScope(("backend/app/autonomy", "backend/tests/autonomy"))
        self.assertEqual(
            scope.validate(["backend/app/autonomy/policy.py"]),
            ("backend/app/autonomy/policy.py",),
        )
        with self.assertRaises(PolicyViolation):
            scope.validate(["backend/app/main.py"])
        self.assertTrue(is_prohibited_path("backend/.env"))
        self.assertTrue(is_prohibited_path("backend/secrets/api-token.txt"))
        self.assertFalse(is_prohibited_path("backend/app/services/pipeline.py"))

    def test_redaction_handles_text_and_nested_artifacts(self) -> None:
        text = (
            "OPENAI_API_KEY=sk-proj-123456789 and Authorization: Bearer abc123 "
            "and provider echo sk-proj-****************qDYA"
        )
        redacted = redact_text(text)
        self.assertNotIn("sk-proj-123456789", redacted)
        self.assertNotIn("qDYA", redacted)
        self.assertNotIn("Bearer abc123", redacted)
        artifact = redact_mapping({"env": {"DATABASE_URL": "postgres://secret"}})
        self.assertEqual(artifact["env"]["DATABASE_URL"], "[REDACTED]")

    def test_bounded_retry_and_escalation_policy(self) -> None:
        policy = BoundedExecutionPolicy()
        self.assertTrue(policy.allow_replan().allowed)
        policy.record_replan()
        self.assertFalse(policy.allow_replan().allowed)
        self.assertTrue(policy.retry_decision(FailureClass.TIMEOUT, 0).allowed)
        self.assertFalse(policy.retry_decision(FailureClass.AUTHENTICATION, 0).allowed)
        policy.record_escalation("luna", "terra")
        self.assertFalse(policy.allow_escalation("luna", "terra").allowed)
        self.assertFalse(policy.allow_escalation("luna", "sol").allowed)


if __name__ == "__main__":
    unittest.main()
