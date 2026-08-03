import os
import pytest

# 測試直接連本機 Docker 的 db service（port 5432）
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://stockuser:stockpass@localhost:5432/stockdb",
)


@pytest.fixture(scope="session", autouse=True)
def set_database_url():
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL


@pytest.fixture
def conn():
    from app.db.connection import get_connection
    c = get_connection()
    c.autocommit = True
    yield c
    c.close()
