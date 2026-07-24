"""Temporary-Git-repository tests for controller-owned workspace safety."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from app.autonomy.policy import TaskScope
from app.autonomy.workspace import GitWorkspace, WorkspaceError


def git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ("git", *arguments),
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


class WorkspaceTests(unittest.TestCase):
    """Verify snapshots and commits in isolated repositories only."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        git(self.root, "init", "-b", "autonomy/test")
        git(self.root, "config", "user.email", "test@example.com")
        git(self.root, "config", "user.name", "Autonomy Test")
        (self.root / "README.md").write_text("initial\n", encoding="utf-8")
        git(self.root, "add", "--", "README.md")
        git(self.root, "commit", "-m", "initial")
        self.workspace = GitWorkspace(self.root)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_snapshot_detects_changed_files_and_branch(self) -> None:
        before = self.workspace.snapshot()
        (self.root / "backend").mkdir()
        (self.root / "backend" / "new.py").write_text("value = 1\n", encoding="utf-8")
        after = self.workspace.snapshot()
        self.assertEqual(before.branch, "autonomy/test")
        self.assertNotEqual(before.diff_hash, after.diff_hash)
        self.assertEqual(after.changed_files, ("backend/new.py",))

    def test_controller_commit_stages_only_explicit_paths(self) -> None:
        before = self.workspace.snapshot()
        (self.root / "backend").mkdir()
        (self.root / "backend" / "new.py").write_text("value = 1\n", encoding="utf-8")
        result = self.workspace.controller_commit(
            "feat: add bounded worker output",
            intended_paths=("backend/new.py",),
            before=before,
            expected_branch="autonomy/test",
            expected_head=before.head,
            scope=TaskScope(("backend",)),
        )
        self.assertEqual(result.branch, "autonomy/test")
        self.assertEqual(self.workspace.snapshot().changed_files, ())
        self.assertEqual(
            git(self.root, "show", "--format=%s", "-s"), "feat: add bounded worker output"
        )

    def test_commit_refuses_unrelated_changes_and_prohibited_paths(self) -> None:
        before = self.workspace.snapshot()
        (self.root / "backend.py").write_text("ok\n", encoding="utf-8")
        (self.root / ".env").write_text("OPENAI_API_KEY=secret\n", encoding="utf-8")
        with self.assertRaises(WorkspaceError):
            self.workspace.controller_commit(
                "feat: unsafe",
                intended_paths=("backend.py",),
                before=before,
                scope=TaskScope(("backend.py",)),
            )
        self.assertEqual(self.workspace.snapshot().head, before.head)

    def test_commit_preserves_unrelated_baseline_dirty_paths(self) -> None:
        (self.root / "notes.txt").write_text("preserve me\n", encoding="utf-8")
        before = self.workspace.snapshot()
        (self.root / "backend").mkdir()
        (self.root / "backend" / "new.py").write_text("value = 1\n", encoding="utf-8")

        result = self.workspace.controller_commit(
            "feat: commit only intended controller work",
            intended_paths=("backend/new.py",),
            before=before,
            expected_branch="autonomy/test",
            expected_head=before.head,
            scope=TaskScope(("backend",)),
        )

        self.assertEqual(result.changed_files, ("backend/new.py",))
        self.assertEqual(self.workspace.snapshot().changed_files, ("notes.txt",))
        self.assertEqual((self.root / "notes.txt").read_text(encoding="utf-8"), "preserve me\n")

    def test_adopting_baseline_dirty_path_requires_explicit_flag(self) -> None:
        (self.root / "existing.txt").write_text("partial work\n", encoding="utf-8")
        before = self.workspace.snapshot()

        with self.assertRaisesRegex(WorkspaceError, "explicit approval"):
            self.workspace.controller_commit(
                "feat: adopt partial work",
                intended_paths=("existing.txt",),
                before=before,
                scope=TaskScope(("existing.txt",)),
            )

        result = self.workspace.controller_commit(
            "feat: adopt partial work",
            intended_paths=("existing.txt",),
            before=before,
            expected_branch="autonomy/test",
            expected_head=before.head,
            scope=TaskScope(("existing.txt",)),
            adopt_preexisting_paths=True,
        )

        self.assertEqual(result.changed_files, ("existing.txt",))
        self.assertEqual(self.workspace.snapshot().changed_files, ())

    def test_post_worker_guard_rejects_branch_or_commit_changes(self) -> None:
        before = self.workspace.snapshot()
        git(self.root, "checkout", "-b", "other")
        with self.assertRaises(WorkspaceError):
            self.workspace.verify_post_worker(before, scope=TaskScope(("backend",)))

    def test_post_worker_guard_accepts_scoped_dirty_output(self) -> None:
        before = self.workspace.snapshot()
        (self.root / "backend").mkdir()
        (self.root / "backend" / "worker.py").write_text("pass\n", encoding="utf-8")
        after = self.workspace.verify_post_worker(
            before,
            expected_branch="autonomy/test",
            expected_head=before.head,
            scope=TaskScope(("backend",)),
        )
        self.assertEqual(after.changed_files, ("backend/worker.py",))


if __name__ == "__main__":
    unittest.main()
