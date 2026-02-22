#!/usr/bin/env python3
"""Weekly content moderation scan for AgentPier.

Scans all active listings against the current content filter.
Reports violations, flags new evasion patterns, and optionally removes listings.

Usage:
    python3 scripts/moderation_scan.py [--dry-run] [--remove]

Output: JSON report to stdout.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.content_filter import check_listing_content, normalize_text


TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")


def get_all_active_listings(table):
    """Scan for all active listings."""
    listings = []
    scan_kwargs = {
        "FilterExpression": Attr("SK").eq("META") & Attr("status").eq("active") & Attr("PK").begins_with("LISTING#"),
    }
    while True:
        response = table.scan(**scan_kwargs)
        listings.extend(response.get("Items", []))
        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
    return listings


def scan_listing(listing):
    """Run a listing through the content filter. Returns violation info or None."""
    title = listing.get("title", "")
    description = listing.get("description", "")
    tags = listing.get("tags", [])

    is_clean, flagged_categories = check_listing_content(title, description, tags)

    if not is_clean:
        return {
            "listing_id": listing.get("listing_id", listing["PK"].replace("LISTING#", "")),
            "title": title,
            "posted_by": listing.get("posted_by", "unknown"),
            "agent_name": listing.get("agent_name", ""),
            "created_at": listing.get("created_at", ""),
            "flagged_categories": flagged_categories,
            "normalized_title": normalize_text(title),
            "normalized_desc_preview": normalize_text(description)[:200],
        }
    return None


def check_for_evasion_patterns(listings):
    """Analyze clean listings for potential evasion patterns worth investigating.
    
    Looks for suspicious signals that passed the filter:
    - Heavy unicode usage (potential homoglyph evasion)
    - Excessive spacing/punctuation in words (potential splitting evasion)
    - Known bait keywords in otherwise clean content
    """
    suspicious = []
    bait_words = ["services", "available", "contact", "telegram", "discord", "dm me", "fast delivery"]

    for listing in listings:
        title = listing.get("title", "")
        desc = listing.get("description", "")
        combined = f"{title} {desc}".lower()
        signals = []

        # Check unicode density (non-ASCII chars as % of total)
        non_ascii = sum(1 for c in combined if ord(c) > 127)
        if len(combined) > 20 and non_ascii / len(combined) > 0.15:
            signals.append(f"high_unicode_density ({non_ascii}/{len(combined)})")

        # Check for excessive internal spacing (e.g., "c o c a i n e")
        import re
        spaced_words = re.findall(r'\b\w(?:\s\w){3,}\b', combined)
        if spaced_words:
            signals.append(f"spaced_out_words: {spaced_words[:3]}")

        # Check bait keyword density
        bait_count = sum(1 for w in bait_words if w in combined)
        if bait_count >= 3:
            signals.append(f"bait_keyword_cluster ({bait_count} matches)")

        if signals:
            suspicious.append({
                "listing_id": listing.get("listing_id", listing["PK"].replace("LISTING#", "")),
                "title": title[:80],
                "signals": signals,
            })

    return suspicious


def remove_listing(table, listing_id):
    """Mark a listing as removed by moderation."""
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


def main():
    parser = argparse.ArgumentParser(description="AgentPier weekly moderation scan")
    parser.add_argument("--dry-run", action="store_true", help="Report only, don't remove anything")
    parser.add_argument("--remove", action="store_true", help="Auto-remove flagged listings")
    args = parser.parse_args()

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.Table(TABLE_NAME)

    # Get all active listings
    listings = get_all_active_listings(table)

    # Scan each listing
    violations = []
    clean_listings = []
    for listing in listings:
        result = scan_listing(listing)
        if result:
            violations.append(result)
        else:
            clean_listings.append(listing)

    # Check clean listings for evasion patterns
    suspicious = check_for_evasion_patterns(clean_listings)

    # Remove flagged listings if requested
    removed = []
    if args.remove and not args.dry_run:
        for v in violations:
            remove_listing(table, v["listing_id"])
            removed.append(v["listing_id"])

    # Build report
    report = {
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "total_listings": len(listings),
        "clean": len(clean_listings),
        "violations": len(violations),
        "suspicious_evasion": len(suspicious),
        "removed": removed,
        "dry_run": args.dry_run or not args.remove,
        "violation_details": violations,
        "evasion_candidates": suspicious,
        "filter_recommendations": [],
    }

    # Generate filter recommendations
    if violations:
        cats = {}
        for v in violations:
            for cat in v["flagged_categories"]:
                cats[cat] = cats.get(cat, 0) + 1
        report["filter_recommendations"].append(
            f"Existing filters caught {len(violations)} listings. Top categories: "
            + ", ".join(f"{c} ({n})" for c, n in sorted(cats.items(), key=lambda x: -x[1]))
        )

    if suspicious:
        report["filter_recommendations"].append(
            f"{len(suspicious)} listings show potential evasion signals. "
            "Review evasion_candidates for new pattern ideas."
        )

    if not violations and not suspicious:
        report["filter_recommendations"].append("All clear. No filter updates needed this cycle.")

    print(json.dumps(report, indent=2, default=str))
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
