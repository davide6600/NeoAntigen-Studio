"""Tests for sequence blacklist and homopolymer safety scanning."""
from __future__ import annotations

import pytest

from agent.skills.sequence_safety import (
    run_safety_scan,
    load_blacklist,
    BlacklistEntry,
)


class TestSafeSequence:
    def test_clean_sequence_is_safe(self):
        result = run_safety_scan("ACGU", dry_run=True)
        assert result.is_safe
        assert result.findings == []

    def test_dry_run_flag_preserved(self):
        result = run_safety_scan("ACGU", dry_run=True)
        assert result.dry_run is True


class TestBlacklistDetection:
    def test_toxin_motif_detected(self):
        result = run_safety_scan("PREFIXTOXINMOTIF", dry_run=True)
        findings = [f for f in result.findings if "TOXIN" in f.upper()]
        assert not result.is_safe
        assert len(findings) > 0

    def test_pathogen_motif_detected(self):
        result = run_safety_scan("XPATHOGENY", dry_run=True)
        assert not result.is_safe

    def test_ricin_motif_detected(self):
        result = run_safety_scan("ABCRICINXYZ", dry_run=True)
        assert not result.is_safe


class TestHomopolymerDetection:
    def test_long_homopolymer_detected(self):
        # 10 consecutive same chars should trip the default threshold (9)
        result = run_safety_scan("AAAAAAAAAA", dry_run=True)
        assert not result.is_safe
        assert any("homopolymer" in f.lower() for f in result.findings)

    def test_short_homopolymer_is_safe(self):
        result = run_safety_scan("AAAACGU", dry_run=True)
        assert result.is_safe


class TestLoadBlacklist:
    def test_returns_list_of_blacklist_entries(self):
        entries = load_blacklist()
        assert isinstance(entries, list)
        assert all(isinstance(e, BlacklistEntry) for e in entries)

    def test_default_has_known_motifs(self):
        motifs = {e.motif for e in load_blacklist()}
        assert "TOXIN" in motifs or any("TOXIN" in m for m in motifs)
