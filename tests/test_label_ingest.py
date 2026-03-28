from agent.learnings.store import LearningStore
from agent.skills.label_ingest import ExperimentLabel, ingest_labels


def test_experiment_label_validation() -> None:
    label = ExperimentLabel(
        label_id="lbl-1",
        peptide_id="pep-1",
        assay_type="MS",
        assay_id="assay-1",
        result="positive",
        qc_metrics={"psm_count": 6, "fdr": 0.005},
        uploaded_by="user-1",
        timestamp="2026-03-15T12:00:00Z",
        uncertainty=0.9,
    )
    assert label.assay_type == "MS"


def test_ingest_labels_logs_batch(tmp_path) -> None:
    store = LearningStore(db_path=str(tmp_path / "learnings.db"))
    result = ingest_labels(
        raw_labels=[
            {
                "label_id": "lbl-1",
                "peptide_id": "pep-1",
                "assay_type": "MS",
                "assay_id": "assay-1",
                "result": "positive",
                "qc_metrics": {"psm_count": 5, "fdr": 0.009},
                "uploaded_by": "u1",
                "timestamp": "2026-03-15T12:00:00Z",
                "uncertainty": 0.8,
            }
        ],
        store=store,
    )

    assert result["batch_id"].startswith("batch-")
    assert result["high_uncertainty_peptides"] == ["pep-1"]
