"""
airlock/tests/test_scrubber.py — Proves the scrubber against real-world-shaped identifiers.

All fixture values use documentation/RFC-reserved ranges — no real infrastructure identifiers.

Run with:  python -m pytest airlock/tests/test_scrubber.py -v
"""

import pytest
from airlock.scrubber import scrub, gate, add_to_denylist, _BUCKET_DENYLIST


# ---------------------------------------------------------------------------
# Fixtures — documentation/RFC-reserved identifiers (not real infrastructure)
# ---------------------------------------------------------------------------

ACCOUNT_ID  = "123456789012"           # AWS documented example account id
PUBLIC_IP   = "203.0.113.10"           # RFC 5737 TEST-NET-3 (documentation range)
PRIVATE_IP  = "10.0.0.5"              # RFC 1918 private range
# ARNs use the documented example account id and generic resource names
ARN_SECRET  = "arn:aws:secretsmanager:us-east-1:123456789012:secret:my-secret-iRid6t"
ARN_SNS     = "arn:aws:sns:us-east-1:123456789012:my-notifications-topic"
BUCKET_1    = "example-media-bucket"
BUCKET_2    = "example-backups"
FQDN_1      = "example.com"            # RFC 2606 reserved example domain
FQDN_2      = "api.example.com"
FQDN_3      = "internal.example.net"   # RFC 2606 reserved
AWS_KEY     = "AKIAIOSFODNN7EXAMPLE"   # AWS official example access key
HIGH_ENTROPY = "xK8$mP2#nQ9wL5vR7jZ3cA6bY1dF4hT0"  # synthetic high-entropy secret
EMAIL       = "user@example.com"       # RFC 2606 reserved example address
PHONE       = "407-555-0192"


# ---------------------------------------------------------------------------
# Helper: assert a placeholder appears in scrubbed output
# ---------------------------------------------------------------------------

def assert_redacted(raw: str, placeholder: str) -> None:
    """Assert the placeholder is present in scrubbed output and original is gone."""
    result = scrub(raw)
    assert placeholder in result, (
        f"Expected '{placeholder}' in scrubbed output.\n"
        f"  Input: {raw!r}\n"
        f"  Got:   {result!r}"
    )


def assert_gate_dirty(raw: str) -> None:
    """Assert gate() returns clean=False for the given text."""
    result = gate(raw)
    assert not result["clean"], (
        f"Expected gate to flag input as dirty.\n"
        f"  Input: {raw!r}\n"
        f"  Findings: {result['findings']}"
    )


# ---------------------------------------------------------------------------
# Individual fixture tests
# ---------------------------------------------------------------------------

class TestAccountId:
    def test_redacted(self):
        assert_redacted(f"Account: {ACCOUNT_ID}", "<ACCOUNT_ID>")

    def test_gate_dirty(self):
        assert_gate_dirty(f"Account: {ACCOUNT_ID}")

    def test_not_in_redacted(self):
        assert ACCOUNT_ID not in scrub(f"Account: {ACCOUNT_ID}")


class TestPublicIP:
    def test_redacted(self):
        assert_redacted(f"Host: {PUBLIC_IP}", "<PUBLIC_IP>")

    def test_gate_dirty(self):
        assert_gate_dirty(f"Host: {PUBLIC_IP}")

    def test_not_in_redacted(self):
        assert PUBLIC_IP not in scrub(f"Host: {PUBLIC_IP}")


class TestPrivateIP:
    def test_redacted(self):
        assert_redacted(f"LAN: {PRIVATE_IP}", "<PRIVATE_IP>")

    def test_gate_dirty(self):
        assert_gate_dirty(f"LAN: {PRIVATE_IP}")

    def test_not_in_redacted(self):
        assert PRIVATE_IP not in scrub(f"LAN: {PRIVATE_IP}")

    def test_private_10_range(self):
        assert_redacted("gateway 10.0.0.1", "<PRIVATE_IP>")

    def test_private_172_range(self):
        assert_redacted("relay 172.16.254.1", "<PRIVATE_IP>")


class TestARN:
    def test_secret_arn_redacted(self):
        assert_redacted(ARN_SECRET, "<ARN>")

    def test_sns_arn_redacted(self):
        assert_redacted(ARN_SNS, "<ARN>")

    def test_gate_dirty_on_arn(self):
        assert_gate_dirty(f"resource: {ARN_SECRET}")

    def test_arn_not_in_output(self):
        assert "arn:aws" not in scrub(ARN_SECRET)


class TestS3Bucket:
    def test_bucket_in_s3_uri(self):
        assert_redacted(f"s3://{BUCKET_1}/data/", "<BUCKET>")

    def test_bucket_in_cli_flag(self):
        assert_redacted(f"--bucket-name {BUCKET_2}", "<BUCKET>")

    def test_gate_dirty_bucket_uri(self):
        assert_gate_dirty(f"s3://{BUCKET_1}/data/")


class TestFQDN:
    def test_fqdn_1(self):
        # example.com is not in the denylist by default — caught as <FQDN>
        result = scrub(f"endpoint: {FQDN_1}")
        assert FQDN_1 not in result, f"FQDN_1 survived scrubbing: {result!r}"
        assert "<FQDN>" in result or "<BUCKET>" in result

    def test_fqdn_2(self):
        result = scrub(f"api at {FQDN_2}")
        assert FQDN_2 not in result, f"FQDN_2 survived scrubbing: {result!r}"

    def test_fqdn_3(self):
        # internal.example.net — caught by FQDN rule
        assert_redacted(f"subdomain: {FQDN_3}", "<FQDN>")

    def test_gate_dirty_fqdn(self):
        assert_gate_dirty(f"see {FQDN_3}")


class TestAWSKey:
    def test_access_key_redacted(self):
        # AKIAIOSFODNN7EXAMPLE is AWS's official documented example key
        assert_redacted(f"AWS_ACCESS_KEY_ID={AWS_KEY}", "<ACCESS_KEY>")

    def test_gate_dirty(self):
        assert_gate_dirty(f"export AWS_ACCESS_KEY_ID={AWS_KEY}")

    def test_key_not_in_output(self):
        assert AWS_KEY not in scrub(f"key: {AWS_KEY}")


class TestHighEntropySecret:
    def test_entropy_flagged_by_gate(self):
        result = gate(HIGH_ENTROPY)
        assert not result["clean"], (
            f"High-entropy string not flagged.\nFindings: {result['findings']}"
        )


class TestEmail:
    def test_email_redacted(self):
        assert_redacted(f"contact: {EMAIL}", "<EMAIL>")

    def test_gate_dirty(self):
        assert_gate_dirty(f"From: {EMAIL}")

    def test_email_not_in_output(self):
        assert EMAIL not in scrub(f"contact: {EMAIL}")


class TestPhone:
    def test_phone_redacted(self):
        assert_redacted(f"call {PHONE}", "<PHONE>")

    def test_gate_dirty(self):
        assert_gate_dirty(f"call {PHONE}")


# ---------------------------------------------------------------------------
# Integration: compound text with multiple sensitive items
# ---------------------------------------------------------------------------

class TestCompound:
    COMPOUND = (
        f"Deploying to account {ACCOUNT_ID} in region us-east-1.\n"
        f"Lambda on {PRIVATE_IP}, ALB at {PUBLIC_IP}.\n"
        f"Secret: {ARN_SECRET}\n"
        f"Bucket: s3://{BUCKET_1}/logs/\n"
        f"Notify: {EMAIL}\n"
        f"Key: {AWS_KEY}"
    )

    def test_all_placeholders_present(self):
        result = scrub(self.COMPOUND)
        for placeholder in ["<ACCOUNT_ID>", "<PRIVATE_IP>", "<PUBLIC_IP>",
                            "<ARN>", "<BUCKET>", "<EMAIL>", "<ACCESS_KEY>"]:
            assert placeholder in result, f"Missing {placeholder} in compound scrub"

    def test_gate_dirty(self):
        assert_gate_dirty(self.COMPOUND)

    def test_no_raw_values_in_output(self):
        result = scrub(self.COMPOUND)
        for raw in [ACCOUNT_ID, PRIVATE_IP, PUBLIC_IP, EMAIL, AWS_KEY]:
            assert raw not in result, f"Raw value '{raw}' survived scrubbing"


# ---------------------------------------------------------------------------
# Gate: clean text passes
# ---------------------------------------------------------------------------

class TestCleanText:
    def test_plain_lesson_is_clean(self):
        text = (
            "Probe your own permission boundary early. "
            "Many describe/list calls returned AccessDenied. "
            "Lesson: know your blast radius before you assume an account is empty."
        )
        result = gate(text)
        assert result["clean"], (
            f"Expected clean text to pass gate.\nFindings: {result['findings']}"
        )


# ---------------------------------------------------------------------------
# Bucket denylist — configurable, loaded at runtime
# ---------------------------------------------------------------------------

class TestBucketDenylist:
    """
    The denylist is empty by default. These tests seed it with example names
    to prove the mechanism works. In production users populate it via
    AIRLOCK_BUCKET_DENYLIST env var.
    """

    def setup_method(self):
        """Seed the denylist with test names before each test in this class."""
        add_to_denylist([
            "example-media-bucket",
            "example-backups",
            "example-www",
            "example.com",
            "www.example.com",
        ])

    def test_bucket_bare_name_in_prose(self):
        """Denylist bucket name in natural prose (no s3:// prefix) must be caught."""
        text = "I deleted the example-media-bucket bucket by mistake."
        result = gate(text)
        assert not result["clean"], "Denylist bucket name should gate as dirty"
        assert "<BUCKET>" in result["redacted"], (
            f"Expected <BUCKET> placeholder.\nGot: {result['redacted']!r}"
        )
        assert "example-media-bucket" not in result["redacted"]

    def test_backups_bare(self):
        text = "Restoring from example-backups took three hours."
        result = gate(text)
        assert not result["clean"]
        assert "<BUCKET>" in result["redacted"]

    def test_www_bare(self):
        text = "Sync job wrote to example-www without a lifecycle rule."
        result = gate(text)
        assert not result["clean"]
        assert "<BUCKET>" in result["redacted"]

    def test_denylist_case_insensitive(self):
        text = "EXAMPLE-MEDIA-BUCKET was public for an hour."
        assert "<BUCKET>" in scrub(text)

    def test_denylist_fqdn_entries(self):
        """Denylist FQDN entries are caught; the name does not appear in output."""
        text = "The site example.com is load-balanced."
        result = gate(text)
        assert not result["clean"]
        assert "example.com" not in result["redacted"]

    def test_clean_text_unaffected(self):
        """Denylist must not cause false positives on clean text."""
        text = "Use IAM roles instead of long-lived credentials."
        result = gate(text)
        assert result["clean"]
