"""Tests for uncertainty estimation and acquisition ranking."""
from __future__ import annotations

import pytest

from agent.skills.acquisition import (
    PeptideEntry,
    compute_uncertainty,
    rank_batch,
)


def _make(pid: str, score: float, preds: list[float]) -> PeptideEntry:
    return PeptideEntry(
        peptide_id=pid,
        sequence=pid,  # dummy – only used for diversity
        score=score,
        ensemble_predictions=preds,
    )


class TestComputeUncertainty:
    def test_uniform_predictions_max_entropy(self):
        # predictions all 0.5 → binary entropy ≈ ln(2) ≈ 0.693 (nats)
        u = compute_uncertainty([0.5, 0.5, 0.5, 0.5])
        assert 0.60 <= u <= 0.70

    def test_unanimous_predictions_zero_entropy(self):
        u = compute_uncertainty([1.0, 1.0, 1.0])
        assert u < 0.05

    def test_empty_predictions_returns_zero(self):
        assert compute_uncertainty([]) == 0.0

    def test_single_value(self):
        assert compute_uncertainty([0.0]) < 0.01


class TestRankBatch:
    def test_returns_requested_batch_size(self):
        candidates = [_make(f"PEP{i}", float(i) / 10, [0.5, 0.5]) for i in range(20)]
        batch = rank_batch(candidates, batch_size=5)
        assert len(batch) == 5

    def test_empty_candidates_returns_empty(self):
        assert rank_batch([], batch_size=10) == []

    def test_fewer_candidates_than_batch_size(self):
        candidates = [_make("A", 0.8, [0.5, 0.5]), _make("B", 0.9, [0.5, 0.5])]
        batch = rank_batch(candidates, batch_size=10)
        assert len(batch) == 2

    def test_returns_peptide_entries(self):
        candidates = [_make(f"P{i}", 0.5, [0.5, 0.5]) for i in range(5)]
        batch = rank_batch(candidates, batch_size=3)
        assert all(isinstance(e[0], PeptideEntry) for e in batch)

    def test_no_duplicate_ids_in_batch(self):
        candidates = [_make(f"PEP{i}", float(i) / 10, [0.5, 0.5]) for i in range(15)]
        batch = rank_batch(candidates, batch_size=10)
        ids = [e[0].peptide_id for e in batch]
        assert len(ids) == len(set(ids))
