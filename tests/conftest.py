import pytest
import structlog


@pytest.fixture(autouse=True)
def clear_structlog_context():
    structlog.contextvars.clear_contextvars()
    yield
    structlog.contextvars.clear_contextvars()
