"""
tests/conftest.py

Shared pytest fixtures and setup.
Clears structlog context between tests to prevent state leakage.
"""
import pytest
import structlog


@pytest.fixture(autouse=True)
def clear_structlog_context():
    """Reset structlog context vars before every test."""
    structlog.contextvars.clear_contextvars()
    yield
    structlog.contextvars.clear_contextvars()
