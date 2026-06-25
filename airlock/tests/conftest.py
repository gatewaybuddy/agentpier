"""
airlock/tests/conftest.py — Shared test fixtures for the Airlock test suite.

Ensures hermetic isolation between tests by resetting all shared module-level
state before each test:
  - Denylist (scrubber._BUCKET_DENYLIST / _DENYLIST_PATTERN)
  - Server store singleton (server._store)

Without this reset, denylist entries added by one test class (e.g.
TestBucketDenylist) bleed into handler/e2e tests collected in the same
pytest session, causing flaky failures that depend on collection order.
"""

import pytest


@pytest.fixture(autouse=True)
def reset_airlock_state():
    """
    Reset all shared module-level state before each test.
    Runs before every test in the suite regardless of collection order.
    """
    import airlock.scrubber as _scrubber
    import airlock.server as _server

    # Clear denylist before the test
    _scrubber._BUCKET_DENYLIST.clear()
    _scrubber._recompile_denylist()

    # Reset the server store singleton so each test that needs a store
    # creates its own (handler tests replace it via isolated_store fixture)
    _server._store = None

    yield

    # Tear down: clear denylist and store after each test
    _scrubber._BUCKET_DENYLIST.clear()
    _scrubber._recompile_denylist()
    if _server._store is not None:
        try:
            _server._store.close()
        except Exception:
            pass
    _server._store = None
