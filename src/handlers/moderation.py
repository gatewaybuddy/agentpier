"""Content moderation scan handler for AgentPier.

Runs as a scheduled Lambda to scan all active listings against
the current content filter. Flags violations, removes them,
and reports evasion patterns for filter tuning.
"""

import json
import os
import re
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr

from utils.content_filter import check_listing_content, normalize_text

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")

# Bait keywords that often appear in borderline/evasion content
_BAIT_WORDS = ["services", "available", "contact", "telegram", "discord", "dm me",
               "fast delivery", "guaranteed", "cheap", "wholesale"]


def _get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


def _get_all_active_listings(table):
    """Scan for all active listings."""
    listings = []
    scan_kwargs = {
        "FilterExpression": (
            Attr("SK").eq("META")
            & Attr("status").eq("active")
            & Attr("PK").begins_with("LISTING#")
        ),
    }
    while True:
        response = table.scan(**scan_kwargs)
        listings.extend(response.get("Items", []))
        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
    return listings


def _check_evasion_signals(listings):
    """Analyze clean listings for potential filter evasion."""
    suspicious = []
    for listing in listings:
        title = listing.get("title", "")
        desc = listing.get("description", "")
        combined = f"{title} {desc}".lower()
        signals = []

        # High unicode density (potential homoglyph evasion)
        non_ascii = sum(1 for c in combined if ord(c) > 127)
        if len(combined) > 20 and non_ascii / len(combined) > 0.15:
            signals.append(f"high_unicode_density ({non_ascii}/{len(combined)})")

        # Spaced-out words (e.g. "c o c a i n e")
        spaced = re.findall(r'\b\w(?:\s\w){3,}\b', combined)
        if spaced:
            signals.append(f"spaced_out_words: {spaced[:3]}")

        # Bait keyword cluster
        bait_count = sum(1 for w in _BAIT_WORDS if w in combined)
        if bait_count >= 3:
            signals.append(f"bait_keyword_cluster ({bait_count})")

        if signals:
            suspicious.append({
                "listing_id": listing.get("listing_id", ""),
                "title": title[:80],
                "signals": signals,
            })
    return suspicious


def _remove_listing(table, listing_id):
    """Mark listing as removed by moderation."""
    table.update_item(
        Key={"PK": f"LISTING#{listing_id}", "SK": "META"},
        UpdateExpression="SET #s = :s, moderation_removed_at = :t, moderation_reason = :r",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "removed",
            ":t": datetime.now(timezone.utc).isoformat(),
            ":r": "weekly_moderation_scan",
        },
    )


def moderation_scan(event, context):
    """Scheduled moderation scan. Auto-removes violations, reports evasion candidates."""
    table = _get_table()
    listings = _get_all_active_listings(table)

    violations = []
    clean = []

    for listing in listings:
        title = listing.get("title", "")
        desc = listing.get("description", "")
        tags = listing.get("tags", [])

        is_clean, flagged = check_listing_content(title, desc, tags)
        if not is_clean:
            lid = listing.get("listing_id", listing["PK"].replace("LISTING#", ""))
            violations.append({
                "listing_id": lid,
                "title": title[:80],
                "posted_by": listing.get("posted_by", ""),
                "agent_name": listing.get("agent_name", ""),
                "flagged_categories": flagged,
            })
            # Auto-remove
            _remove_listing(table, lid)
        else:
            clean.append(listing)

    # Check for evasion patterns in clean listings
    suspicious = _check_evasion_signals(clean)

    # Category breakdown
    cat_counts = {}
    for v in violations:
        for cat in v["flagged_categories"]:
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

    report = {
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "total_scanned": len(listings),
        "clean": len(clean),
        "violations_found": len(violations),
        "violations_removed": len(violations),
        "suspicious_evasion": len(suspicious),
        "category_breakdown": cat_counts,
        "violation_details": violations,
        "evasion_candidates": suspicious,
    }

    # Log the report to DynamoDB for historical tracking
    table.put_item(Item={
        "PK": "MODERATION#SCAN",
        "SK": datetime.now(timezone.utc).isoformat(),
        "report": json.loads(json.dumps(report, default=str)),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    print(json.dumps(report, indent=2, default=str))
    return report


def moderation_scan_api(event, context):
    """POST /admin/moderation-scan — API-triggered moderation scan.
    
    Requires admin API key via X-Admin-Key header.
    """
    from utils.response import success, error

    admin_key = os.environ.get("ADMIN_API_KEY", "")
    provided = (event.get("headers") or {}).get("x-admin-key", "")

    if not admin_key or provided != admin_key:
        return {"statusCode": 403, "body": json.dumps({"error": "Forbidden"})}

    report = moderation_scan(event, context)
    return success(report)
