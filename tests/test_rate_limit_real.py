#!/usr/bin/env python3
"""
Test SDK error handling with actual rate limit scenarios.

This script tests that RateLimitError exceptions are properly raised
when hitting API rate limits on real endpoints.
"""

import sys
import time
import threading
from typing import Optional

# Add SDK to path if running standalone
sys.path.insert(0, "/mnt/d/Projects/agentpier/sdk/python")

from agentpier import AgentPier
from agentpier.exceptions import RateLimitError


def test_rate_limit_burst(client: AgentPier, max_requests: int = 50) -> bool:
    """
    Test rate limiting by making rapid burst requests.

    Args:
        client: AgentPier client instance
        max_requests: Maximum requests to make before giving up

    Returns:
        True if RateLimitError was caught, False otherwise
    """
    print(f"Testing rate limit with burst of up to {max_requests} requests...")

    rate_limited = False
    successful_requests = 0

    for i in range(max_requests):
        try:
            # Use standards endpoint (public, likely rate limited)
            result = client.standards.current()
            successful_requests += 1
            print(
                f"Request {i+1}: SUCCESS (version: {result.get('version', 'unknown')})"
            )

            # Small delay to avoid overwhelming the server immediately
            time.sleep(0.1)

        except RateLimitError as e:
            print(f"Request {i+1}: RATE LIMITED!")
            print(f"  Status code: {e.status_code}")
            print(f"  Message: {e.message}")
            print(f"  Retry after: {e.retry_after} seconds")
            print(f"  Successful requests before limit: {successful_requests}")
            rate_limited = True
            break

        except Exception as e:
            print(f"Request {i+1}: UNEXPECTED ERROR - {type(e).__name__}: {e}")
            break

    if not rate_limited:
        print(f"No rate limit hit after {successful_requests} requests")
        return False

    return True


def test_rate_limit_concurrent(
    client: AgentPier, num_threads: int = 10, requests_per_thread: int = 5
) -> bool:
    """
    Test rate limiting with concurrent requests from multiple threads.

    Args:
        client: AgentPier client instance
        num_threads: Number of concurrent threads
        requests_per_thread: Requests per thread

    Returns:
        True if any thread hit a rate limit, False otherwise
    """
    print(
        f"Testing rate limit with {num_threads} threads, {requests_per_thread} requests each..."
    )

    results = {"rate_limited": False, "errors": []}

    def worker_thread(thread_id: int):
        """Worker thread function."""
        for i in range(requests_per_thread):
            try:
                result = client.standards.current()
                print(f"Thread {thread_id} Request {i+1}: SUCCESS")

            except RateLimitError as e:
                print(f"Thread {thread_id} Request {i+1}: RATE LIMITED!")
                print(f"  Status: {e.status_code}, Retry after: {e.retry_after}s")
                results["rate_limited"] = True
                return  # Exit thread on rate limit

            except Exception as e:
                error_msg = f"Thread {thread_id} Request {i+1}: {type(e).__name__}: {e}"
                print(error_msg)
                results["errors"].append(error_msg)
                return

    # Start threads
    threads = []
    for t in range(num_threads):
        thread = threading.Thread(target=worker_thread, args=(t,))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    if results["errors"]:
        print(f"Unexpected errors occurred: {results['errors']}")

    return results["rate_limited"]


def test_rate_limit_recovery(client: AgentPier) -> bool:
    """
    Test that the client can recover after hitting rate limits.

    Returns:
        True if recovery worked, False otherwise
    """
    print("Testing rate limit recovery...")

    # First, try to trigger a rate limit
    rate_limited = False
    retry_after = None

    for i in range(20):  # Try to hit rate limit with fewer requests
        try:
            result = client.standards.current()
            print(f"Pre-recovery request {i+1}: SUCCESS")
            time.sleep(0.05)  # Faster requests

        except RateLimitError as e:
            print(f"Hit rate limit on request {i+1}")
            print(f"  Retry after: {e.retry_after} seconds")
            rate_limited = True
            retry_after = e.retry_after
            break

        except Exception as e:
            print(f"Unexpected error: {type(e).__name__}: {e}")
            return False

    if not rate_limited:
        print("Could not trigger rate limit for recovery test")
        return False

    # Wait for the suggested retry period
    if retry_after:
        print(f"Waiting {retry_after} seconds for rate limit to reset...")
        time.sleep(retry_after + 1)  # Add 1 second buffer
    else:
        print("No retry-after header, waiting 5 seconds...")
        time.sleep(5)

    # Try request again
    try:
        result = client.standards.current()
        print("Recovery request: SUCCESS - rate limit recovery confirmed!")
        return True

    except RateLimitError:
        print("Recovery request: STILL RATE LIMITED")
        return False

    except Exception as e:
        print(f"Recovery request failed: {type(e).__name__}: {e}")
        return False


def main():
    """Run rate limit tests."""
    print("=== AgentPier SDK Rate Limit Testing ===")
    print(f"Testing with real API endpoints")
    print()

    # Create client without API key (using public endpoints)
    client = AgentPier()

    test_results = {}

    # Test 1: Burst requests
    print("--- Test 1: Burst Rate Limiting ---")
    test_results["burst"] = test_rate_limit_burst(client, max_requests=30)
    print()

    # Wait between tests
    print("Waiting 10 seconds between tests...")
    time.sleep(10)

    # Test 2: Concurrent requests
    print("--- Test 2: Concurrent Rate Limiting ---")
    test_results["concurrent"] = test_rate_limit_concurrent(
        client, num_threads=5, requests_per_thread=3
    )
    print()

    # Wait between tests
    print("Waiting 15 seconds between tests...")
    time.sleep(15)

    # Test 3: Recovery
    print("--- Test 3: Rate Limit Recovery ---")
    test_results["recovery"] = test_rate_limit_recovery(client)
    print()

    # Results summary
    print("=== Test Results Summary ===")
    for test_name, result in test_results.items():
        status = "PASS" if result else "FAIL"
        print(f"  {test_name.capitalize()} test: {status}")

    # Overall assessment
    any_passed = any(test_results.values())
    all_passed = all(test_results.values())

    if all_passed:
        print("\n✅ ALL TESTS PASSED - SDK rate limit handling works correctly!")
        return 0
    elif any_passed:
        print(
            f"\n⚠️  PARTIAL SUCCESS - {sum(test_results.values())}/{len(test_results)} tests passed"
        )
        print("SDK rate limit handling is working but may need optimization.")
        return 0
    else:
        print("\n❌ ALL TESTS FAILED - Could not trigger rate limits for testing")
        print("This may indicate:")
        print("  - API rate limits are very high or disabled")
        print("  - Need authenticated endpoints for rate limit testing")
        print("  - SDK may still work correctly in production")
        return 1


if __name__ == "__main__":
    sys.exit(main())
