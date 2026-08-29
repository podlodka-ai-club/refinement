"""Общие фикстуры."""

import pytest
import tempfile
from pathlib import Path
from curator.backend.local import LocalBackend


@pytest.fixture
def tmpdb():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        backend = LocalBackend(str(db_path))
        yield backend


@pytest.fixture
def tmpdir():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)