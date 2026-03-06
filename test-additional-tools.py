#!/usr/bin/env python3
"""
Test additional MCP tools that weren't tested in the main script
"""

import json
import subprocess
import os
import sys

API_KEY = "ap_live_oW3tHjdJ4Y17wEz5Upu4iQBD4ifcnlQPB6N6nTctOaY"
EXISTING_LISTING_ID = "lst_c9b55d72bbd5"  # The first listing we created via REST API


def send_message(proc, msg_id, method, params=None):
    message = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params:
        message["params"] = params

    msg_str = json.dumps(message) + "\n"
    print(f"Sending: {msg_str.strip()}", file=sys.stderr)
    proc.stdin.write(msg_str)
    proc.stdin.flush()

    response_line = proc.stdout.readline()
    if response_line:
        print(f"Received: {response_line.strip()}", file=sys.stderr)
        try:
            return json.loads(response_line)
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON: {e}", file=sys.stderr)
            return None
    return None


def main():
    env = os.environ.copy()
    env["AGENTPIER_API_KEY"] = API_KEY

    cmd = ["node", "server.js"]
    cwd = "/mnt/d/Projects/agentpier/mcp"

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            env=env,
        )

        # Initialize
        send_message(
            proc,
            1,
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "0.1.0"},
            },
        )

        # Test get_listing
        print("\n=== Test get_listing ===", file=sys.stderr)
        response = send_message(
            proc,
            2,
            "tools/call",
            {"name": "get_listing", "arguments": {"listing_id": EXISTING_LISTING_ID}},
        )

        if response and "result" in response:
            print("get_listing: SUCCESS", file=sys.stderr)
        else:
            print(f"get_listing: FAILED - {response}", file=sys.stderr)

        # Test update_listing
        print("\n=== Test update_listing ===", file=sys.stderr)
        response = send_message(
            proc,
            3,
            "tools/call",
            {
                "name": "update_listing",
                "arguments": {
                    "listing_id": EXISTING_LISTING_ID,
                    "availability": "Updated via MCP protocol test",
                },
            },
        )

        if response and "result" in response:
            print("update_listing: SUCCESS", file=sys.stderr)
        else:
            print(f"update_listing: FAILED - {response}", file=sys.stderr)

        # Test rotate_key (but don't actually use it as it would break other tests)
        print("\n=== Test register tool (simulated) ===", file=sys.stderr)
        print(
            "NOTE: Skipping register tool test as it would create another account",
            file=sys.stderr,
        )

        # Test the ACE-T trust system tools (these might not have endpoints implemented yet)
        print("\n=== Test register_agent ===", file=sys.stderr)
        response = send_message(
            proc,
            4,
            "tools/call",
            {
                "name": "register_agent",
                "arguments": {
                    "agent_name": "Test-ACE-Agent",
                    "capabilities": ["test", "mcp"],
                    "declared_scope": "testing",
                    "description": "Test agent for ACE-T system",
                },
            },
        )

        if (
            response
            and "result" in response
            and not response.get("result", {}).get("isError")
        ):
            print("register_agent: SUCCESS", file=sys.stderr)
        else:
            print(
                f"register_agent: Expected to fail (not implemented) - {response}",
                file=sys.stderr,
            )

        # Test query_trust
        print("\n=== Test query_trust ===", file=sys.stderr)
        response = send_message(
            proc,
            5,
            "tools/call",
            {"name": "query_trust", "arguments": {"agent_id": "test-agent-123"}},
        )

        if (
            response
            and "result" in response
            and not response.get("result", {}).get("isError")
        ):
            print("query_trust: SUCCESS", file=sys.stderr)
        else:
            print(
                f"query_trust: Expected to fail (not implemented) - {response}",
                file=sys.stderr,
            )

        # Test search_agents
        print("\n=== Test search_agents ===", file=sys.stderr)
        response = send_message(
            proc,
            6,
            "tools/call",
            {"name": "search_agents", "arguments": {"min_score": 0.0, "limit": 10}},
        )

        if (
            response
            and "result" in response
            and not response.get("result", {}).get("isError")
        ):
            print("search_agents: SUCCESS", file=sys.stderr)
        else:
            print(
                f"search_agents: Expected to fail (not implemented) - {response}",
                file=sys.stderr,
            )

        return True

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return False
    finally:
        if "proc" in locals():
            proc.terminate()
            proc.wait()


if __name__ == "__main__":
    main()
