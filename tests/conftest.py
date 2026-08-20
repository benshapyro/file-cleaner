import os
import time
from pathlib import Path

import pytest


@pytest.fixture
def aged_file():
    def create(path: Path, content: bytes = b"content", days: int = 31) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        timestamp = time.time() - days * 86400
        os.utime(path, (timestamp, timestamp))
        return path

    return create
