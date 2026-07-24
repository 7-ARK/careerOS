"""Tests for scoped worker file operations."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.autonomy.operations import (
    FileOperation,
    FileOperationApplier,
    FileOperationKind,
)


def sha256(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def test_applier_writes_new_file_inside_scope(tmp_path: Path) -> None:
    applier = FileOperationApplier(tmp_path)
    operation = FileOperation(
        kind=FileOperationKind.WRITE,
        path="frontend/tests/new.spec.ts",
        content="test('safe', () => {});\n",
    )

    result = applier.apply([operation], allowed_paths=["frontend/tests"])

    assert (tmp_path / "frontend" / "tests" / "new.spec.ts").read_text(
        encoding="utf-8"
    ) == "test('safe', () => {});\n"
    assert result[0].before_sha256 is None


def test_applier_replaces_exact_text_with_hash_guard(tmp_path: Path) -> None:
    path = tmp_path / "frontend" / "app.ts"
    path.parent.mkdir()
    path.write_text("const port = 3000;\n", encoding="utf-8")
    operation = FileOperation(
        kind=FileOperationKind.REPLACE,
        path="frontend/app.ts",
        expected_sha256=sha256("const port = 3000;\n"),
        old_text="3000",
        new_text="5173",
    )

    FileOperationApplier(tmp_path).apply([operation], allowed_paths=["frontend/app.ts"])

    assert path.read_text(encoding="utf-8") == "const port = 5173;\n"


def test_applier_rejects_stale_hash_without_editing(tmp_path: Path) -> None:
    path = tmp_path / "app.py"
    path.write_text("original\n", encoding="utf-8")
    operation = FileOperation(
        kind=FileOperationKind.REPLACE,
        path="app.py",
        expected_sha256="0" * 64,
        old_text="original",
        new_text="changed",
    )

    with pytest.raises(ValueError, match="stale"):
        FileOperationApplier(tmp_path).apply([operation], allowed_paths=["app.py"])

    assert path.read_text(encoding="utf-8") == "original\n"


@pytest.mark.parametrize(
    "path",
    [
        "../outside.py",
        ".env",
        "backend/.env.local",
        "secrets/provider_credentials.json",
        "private_key.pem",
    ],
)
def test_applier_rejects_unsafe_or_secret_paths(tmp_path: Path, path: str) -> None:
    operation = FileOperation(
        kind=FileOperationKind.WRITE,
        path=path,
        content="unsafe",
    )

    with pytest.raises(ValueError):
        FileOperationApplier(tmp_path).apply([operation], allowed_paths=["."])


def test_applier_rejects_operations_outside_declared_scope(tmp_path: Path) -> None:
    operation = FileOperation(
        kind=FileOperationKind.WRITE,
        path="backend/app/unrelated.py",
        content="pass\n",
    )

    with pytest.raises(ValueError, match="outside task scope"):
        FileOperationApplier(tmp_path).apply(
            [operation],
            allowed_paths=["frontend/tests"],
        )


def test_applier_rejects_multiple_operations_for_the_same_file(tmp_path: Path) -> None:
    operations = [
        FileOperation(
            kind=FileOperationKind.WRITE,
            path="feature.txt",
            content="first\n",
        ),
        FileOperation(
            kind=FileOperationKind.WRITE,
            path="feature.txt",
            content="second\n",
        ),
    ]

    with pytest.raises(ValueError, match="multiple operations"):
        FileOperationApplier(tmp_path).apply(
            operations,
            allowed_paths=["feature.txt"],
        )

    assert not (tmp_path / "feature.txt").exists()
