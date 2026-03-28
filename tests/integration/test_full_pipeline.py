"""
Synthetic end-to-end integration fixture.

Covers the critical path:
  ingest 30 synthetic labels with uncertainty
  → check retrain recommendation
  → simulate stage_retrain
  → generate_staging_report
  → assert report file exists and contains APPROVE_MODEL_PROMOTION token
"""
from __future__ import annotations

import json
import random
from datetime import datetime, UTC
from pathlib import Path

import pytest

from agent.learnings.store import LearningStore
from agent.skills.label_ingest import ingest_labels
from agent.skills.acquisition import PeptideEntry, rank_batch
from agent.skills.ml_trainer import generate_staging_report, RetrainProposal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def store(tmp_path):
    return LearningStore(db_path=str(tmp_path / "integration.db"))


@pytest.fixture()
def staging_dir(tmp_path):
    d = tmp_path / "staging"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _synthetic_labels(n: int = 30) -> list[dict]:
    rng = random.Random(42)
    assay_types = ["MS", "TSCAN", "MULTIMER", "ELISPOT"]
    results = ["positive", "negative", "ambiguous"]
    labels = []
    for i in range(n):
        labels.append({
            "label_id": f"lbl-{i:04d}",
            "peptide_id": f"PEP_{i:04d}",
            "assay_type": rng.choice(assay_types),
            "assay_id": f"ASSAY-{i:03d}",
            "result": rng.choice(results),
            "score": round(rng.uniform(0.0, 1.0), 3),
            "uploaded_by": "synthetic-generator",
            "timestamp": datetime.now(UTC).isoformat(),
            "uncertainty": round(rng.uniform(0.0, 0.5), 3),
        })
    return labels


def _synthetic_peptides(n: int = 20) -> list[PeptideEntry]:
    rng = random.Random(99)
    return [
        PeptideEntry(
            peptide_id=f"PEP_{i:04d}",
            sequence="".join(rng.choices("ACDEFGHIKLMNPQRSTVWY", k=9)),
            score=round(rng.uniform(0.0, 1.0), 3),
            ensemble_predictions=[rng.uniform(0.0, 1.0) for _ in range(5)],
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------

class TestFullPipeline:
    def test_ingest_30_labels_records_to_store(self, store):
        labels = _synthetic_labels(30)
        result = ingest_labels(labels, store=store)
        assert result["total"] == 30
        assert result["schema_errors"] == []

    def test_retrain_recommended_after_sufficient_labels(self, store):
        labels = _synthetic_labels(30)
        ingest_labels(labels, store=store)
        summary = store.suggest_retrain()
        # With 30 labels ingested a retrain should be recommended
        assert summary["recommend_retrain"] is True

    def test_acquisition_batch_selects_diverse_peptides(self):
        peptides = _synthetic_peptides(20)
        batch = rank_batch(peptides, batch_size=8)
        assert len(batch) == 8
        ids = [e[0].peptide_id for e in batch]
        # All selected peptides should be unique
        assert len(ids) == len(set(ids))

    def test_staging_report_written(self, store, staging_dir):
        proposal = RetrainProposal(
            training_data_id="ds-synth-001",
            target_stage="staging",
            model_version="v-synth-001",
            notes="integration test",
        )
        metrics = {"auc_roc": 0.82, "precision": 0.77, "recall": 0.71, "f1": 0.74}
        explainability = {
            "top_features": ["length", "hydrophobicity", "charge"],
            "decision_rules": ["length > 8 → binding_likely"],
            "misclassifications": [{"peptide_id": "PEP_0001", "predicted": 0, "actual": 1}],
        }
        report_path = generate_staging_report(
            proposal, metrics, explainability, output_dir=str(staging_dir)
        )
        assert report_path is not None
        report_file = Path(report_path)
        assert report_file.exists()

    def test_staging_report_contains_promotion_token(self, store, staging_dir):
        proposal = RetrainProposal(
            training_data_id="ds-synth-002",
            target_stage="staging",
            model_version="v-synth-002",
            notes="integration test 2",
        )
        metrics = {"auc_roc": 0.85, "precision": 0.80, "recall": 0.75, "f1": 0.77}
        explainability = {
            "top_features": ["hydrophobicity"],
            "decision_rules": [],
            "misclassifications": [],
        }
        report_path = generate_staging_report(
            proposal, metrics, explainability, output_dir=str(staging_dir)
        )
        content = Path(report_path).read_text()
        assert "APPROVE_MODEL_PROMOTION" in content
