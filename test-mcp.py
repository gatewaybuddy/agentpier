#!/usr/bin/env python3
"""
Test script for AgentPier MCP server
Sends JSON-RPC messages via stdin and reads responses from stdout
"""

import json
import subprocess
import os
import sys

# API key from previous registration step
API_KEY = "ap_live_oW3tHjdJ4Y17wEz5Upu4iQBD4ifcnlQPB6N6nTctOaY"


def send_message(proc, msg_id, method, params=None):
    """Send a JSON-RPC message to the MCP server"""
    message = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params:
        message["params"] = params

    msg_str = json.dumps(message) + "\n"
    print(f"Sending: {msg_str.strip()}", file=sys.stderr)
    proc.stdin.write(msg_str)
    proc.stdin.flush()

    # Read response
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
    # Set environment variables
    env = os.environ.copy()
    env["AGENTPIER_API_KEY"] = API_KEY

    # Start the MCP server process
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

        print("Starting MCP server...", file=sys.stderr)

        # 1. Initialize the connection
        print("\n=== Step 1: Initialize ===", file=sys.stderr)
        response = send_message(
            proc,
            1,
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "0.1.0"},
            },
        )

        if not response or "error" in response:
            print(f"Initialization failed: {response}", file=sys.stderr)
            return False

        # 2. List available tools
        print("\n=== Step 2: List Tools ===", file=sys.stderr)
        response = send_message(proc, 2, "tools/list")

        if not response or "error" in response:
            print(f"List tools failed: {response}", file=sys.stderr)
            return False

        tools = response.get("result", {}).get("tools", [])
        print(f"Found {len(tools)} tools:", file=sys.stderr)
        for tool in tools:
            print(
                f"  - {tool.get('name')}: {tool.get('description', 'No description')}",
                file=sys.stderr,
            )

        # 3. Test search_listings tool
        print("\n=== Step 3: Test search_listings tool ===", file=sys.stderr)
        response = send_message(
            proc,
            3,
            "tools/call",
            {
                "name": "search_listings",
                "arguments": {"category": "it_support", "state": "FL"},
            },
        )

        if response and "result" in response:
            print("search_listings: SUCCESS", file=sys.stderr)
        else:
            print(f"search_listings: FAILED - {response}", file=sys.stderr)

        # 4. Test get_profile tool
        print("\n=== Step 4: Test get_profile tool ===", file=sys.stderr)
        response = send_message(
            proc, 4, "tools/call", {"name": "get_profile", "arguments": {}}
        )

        if response and "result" in response:
            print("get_profile: SUCCESS", file=sys.stderr)
        else:
            print(f"get_profile: FAILED - {response}", file=sys.stderr)

        # 5. Test create_listing tool
        print("\n=== Step 5: Test create_listing tool ===", file=sys.stderr)
        response = send_message(
            proc,
            5,
            "tools/call",
            {
                "name": "create_listing",
                "arguments": {
                    "title": "MCP Test Listing via Protocol",
                    "category": "other",
                    "description": "This listing was created via MCP protocol test",
                    "tags": ["mcp", "protocol", "test"],
                    "location": {"state": "NY", "city": "New York"},
                },
            },
        )

        mcp_listing_id = None
        if response and "result" in response:
            print("create_listing: SUCCESS", file=sys.stderr)
            try:
                result_data = json.loads(response["result"]["content"][0]["text"])
                mcp_listing_id = result_data.get("id")
                print(f"Created listing: {mcp_listing_id}", file=sys.stderr)
            except:
                pass
        else:
            print(f"create_listing: FAILED - {response}", file=sys.stderr)

        # 6. Test get_trust tool
        print("\n=== Step 6: Test get_trust tool ===", file=sys.stderr)
        response = send_message(
            proc,
            6,
            "tools/call",
            {"name": "get_trust", "arguments": {"user_id": "2e1149c9f50e"}},
        )

        if response and "result" in response:
            print("get_trust: SUCCESS", file=sys.stderr)
        else:
            print(f"get_trust: FAILED - {response}", file=sys.stderr)

        # 7. Clean up: delete the MCP-created listing if it exists
        if mcp_listing_id:
            print(
                f"\n=== Step 7: Clean up - Delete {mcp_listing_id} ===", file=sys.stderr
            )
            response = send_message(
                proc,
                7,
                "tools/call",
                {"name": "delete_listing", "arguments": {"listing_id": mcp_listing_id}},
            )

            if response and "result" in response:
                print("delete_listing: SUCCESS", file=sys.stderr)
            else:
                print(f"delete_listing: FAILED - {response}", file=sys.stderr)

        return True

    except Exception as e:
        print(f"Error running test: {e}", file=sys.stderr)
        return False
    finally:
        if "proc" in locals():
            proc.terminate()
            proc.wait()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
