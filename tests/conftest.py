from pathlib import Path
import uuid

import pytest
from services.api.config import get_settings

collect_ignore = ["pytest_tmp", "pytest_tmp_runs", "tmp_paths"]


@pytest.fixture
def tmp_path():
    tmp_root = Path(__file__).resolve().parent / "tmp_paths"
    tmp_root.mkdir(parents=True, exist_ok=True)
    path = tmp_root / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
