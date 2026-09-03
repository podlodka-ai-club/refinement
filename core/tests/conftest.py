"""Общие фикстуры."""

import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def tmpdir():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)