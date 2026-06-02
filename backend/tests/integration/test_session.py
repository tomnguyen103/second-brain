import os
import pytest
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB")


def test_connects_and_has_vector(db_session):
    assert db_session.execute(text("SELECT 1")).scalar() == 1
    ext = db_session.execute(
        text("SELECT extname FROM pg_extension WHERE extname='vector'")).scalar()
    assert ext == "vector"
