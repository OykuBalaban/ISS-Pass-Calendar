import os
import sys
from datetime import datetime, timezone

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from isspass import tle
from isspass.models import Location
from isspass.repository import Repository

SAMPLE_PATH = os.path.join(ROOT, "data", "iss_sample_2014.tle")
with open(SAMPLE_PATH, encoding="utf-8") as f:
    SAMPLE_TEXT = f.read()
T0 = datetime(2014, 1, 21, 12, 0, tzinfo=timezone.utc)
MUNICH = Location("Munich", 48.1351, 11.582, "Europe/Berlin", id=1)


@pytest.fixture
def sample():
    return tle.parse(SAMPLE_TEXT)


@pytest.fixture
def repo():
    return Repository(":memory:")
