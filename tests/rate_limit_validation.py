#!/usr/bin/env python3
"""
Comprehensive rate limit error handling validation.

This test combines real API calls with mocked rate limit scenarios
to thoroughly validate SDK rate limit error handling.
"""

import sys
import time
import requests_mock

sys.path.insert(0, "/mnt/d/Projects/agentpier/sdk/python")

from agentpier import AgentPier
from agentpier.exceptions import RateLimitError


def test_real_api_baseline():
    """Test that real API calls work as baseline."""
    print("=== Testing Real API Baseline ===")

    client = AgentPier()

    try:
        result = client.standards.current()
        print(f"✅ Real API call successful (version: {result.version})")
        return True
    except Exception as e:
        print(f"❌ Real API call failed: {type(e).__name__}: {e}")
        return False


def test_mocked_rate_limit_scenarios():
    """Test rate limit scenarios using mocked responses."""
    print("\n=== Testing Mocked Rate Limit Scenarios ===")

    client = AgentPier()

    with requests_mock.Mocker() as m:
        # Scenario 1: Basic rate limit with retry-after
        m.get(
            "https://api.agentpier.org/standards/current",
            status_code=429,
            headers={"Retry-After": "30"},
            json={
                "error": "rate_limit_exceeded",
                "message": "Too many requests. Please try again later.",
                "retry_after": 30,
            },
        )

        try:
            client.standards.current()
            print("❌ Expected RateLimitError but call succeeded")
            return False
        except RateLimitError as e:
            print(f"✅ Caught RateLimitError correctly:")
            print(f"   Status code: {e.status_code}")
            print(f"   Message: {e.message}")
            print(f"   Retry after: {e.retry_after} seconds")
            if e.status_code == 429 and e.retry_after == 30:
                print("✅ Rate limit details parsed correctly")
            else:
                print("❌ Rate limit details not parsed correctly")
                return False
        except Exception as e:
            print(f"❌ Wrong exception type: {type(e).__name__}: {e}")
            return False

    # Scenario 2: Rate limit without retry-after header
    with requests_mock.Mocker() as m:
        m.get(
            "https://api.agentpier.org/standards/current",
            status_code=429,
            json={"error": "rate_limited", "message": "Rate limit exceeded"},
        )

        try:
            client.standards.current()
            print("❌ Expected RateLimitError but call succeeded")
            return False
        except RateLimitError as e:
            print(f"✅ Caught RateLimitError without retry-after:")
            print(f"   Message: {e.message}")
            print(f"   Retry after: {e.retry_after} (should be None)")
            if e.retry_after is None:
                print("✅ Correctly handled missing retry-after")
            else:
                print("❌ Should have None for retry_after when header missing")
                return False
        except Exception as e:
            print(f"❌ Wrong exception type: {type(e).__name__}: {e}")
            return False

    return True


def test_rate_limit_retry_logic():
    """Test that the SDK retries on appropriate rate limits."""
    print("\n=== Testing Rate Limit Retry Logic ===")

    client = AgentPier()

    with requests_mock.Mocker() as m:
        # First request: rate limited with short retry
        # Second request: success
        m.get(
            "https://api.agentpier.org/standards/current",
            [
                {
                    "status_code": 429,
                    "headers": {"Retry-After": "1"},
                    "json": {
                        "error": "rate_limited",
                        "message": "Rate limited, retry shortly",
                    },
                },
                {
                    "status_code": 200,
                    "json": {
                        "version": "1.0.0",
                        "effective_date": "2026-03-04",
                        "standards": {"agent": {"version": "1.0.0"}},
                    },
                },
            ],
        )

        try:
            start_time = time.time()
            result = client.standards.current()
            elapsed = time.time() - start_time

            print(f"✅ Request succeeded after retry (took {elapsed:.1f}s)")
            print(f"   Result version: {result.version}")

            # Should have taken at least 1 second due to retry delay
            if elapsed >= 1.0:
                print("✅ Retry delay was respected")
                return True
            else:
                print(f"❌ Expected at least 1s delay, but took {elapsed:.1f}s")
                return False

        except Exception as e:
            print(f"❌ Request failed despite retry: {type(e).__name__}: {e}")
            return False


def test_rate_limit_no_retry_on_long_wait():
    """Test that SDK doesn't retry when retry-after is too long."""
    print("\n=== Testing No Retry on Long Wait ===")

    client = AgentPier()

    with requests_mock.Mocker() as m:
        # Rate limit with long retry-after (should not retry)
        m.get(
            "https://api.agentpier.org/standards/current",
            status_code=429,
            headers={"Retry-After": "300"},  # 5 minutes
            json={"error": "rate_limited", "message": "Rate limited for 5 minutes"},
        )

        try:
            start_time = time.time()
            client.standards.current()
            elapsed = time.time() - start_time
            print(f"❌ Expected RateLimitError but call succeeded in {elapsed:.1f}s")
            return False
        except RateLimitError as e:
            elapsed = time.time() - start_time
            print(
                f"✅ Correctly raised RateLimitError without retry (took {elapsed:.1f}s)"
            )
            print(f"   Retry after: {e.retry_after} seconds")

            # Should fail quickly without waiting 5 minutes
            if elapsed < 10:
                print("✅ Did not wait for long retry-after period")
                return True
            else:
                print(f"❌ Took too long ({elapsed:.1f}s), may have retried")
                return False
        except Exception as e:
            print(f"❌ Wrong exception type: {type(e).__name__}: {e}")
            return False


def main():
    """Run all rate limit validation tests."""
    print("AgentPier SDK Rate Limit Error Handling Validation")
    print("=" * 55)

    tests = [
        ("Real API Baseline", test_real_api_baseline),
        ("Mocked Rate Limit Scenarios", test_mocked_rate_limit_scenarios),
        ("Rate Limit Retry Logic", test_rate_limit_retry_logic),
        ("No Retry on Long Wait", test_rate_limit_no_retry_on_long_wait),
    ]

    results = {}

    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * len(test_name) + ":")

        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ Test failed with exception: {type(e).__name__}: {e}")
            results[test_name] = False

    # Summary
    print("\n" + "=" * 55)
    print("Test Results Summary:")
    passed = 0
    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  {status}: {test_name}")
        if result:
            passed += 1

    print(f"\nOverall: {passed}/{len(tests)} tests passed")

    if passed == len(tests):
        print("\n🎉 ALL TESTS PASSED!")
        print("SDK rate limit error handling is working correctly.")
        return True
    else:
        print(f"\n⚠️  {len(tests) - passed} test(s) failed.")
        print("SDK rate limit error handling needs attention.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
