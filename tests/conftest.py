"""
Test configuration — auto-bypass auth for all tests unless marked real_auth.
"""
import uuid
from types import SimpleNamespace

import pytest

FAKE_USER_ID = uuid.UUID("aaaabbbb-cccc-dddd-eeee-ffffaaaabbbb")
FAKE_USER = SimpleNamespace(id=FAKE_USER_ID, email="test@example.com", name="Test User", role="user")


@pytest.fixture(autouse=True)
def override_auth(request):
    """Bypass get_current_user for all tests. Use @pytest.mark.real_auth to opt out."""
    if request.node.get_closest_marker("real_auth"):
        yield
        return
    from api.main import app
    from auth.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)
