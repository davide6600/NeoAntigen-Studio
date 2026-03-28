from agent.learnings.store import LearningRecord, LearningStore


def test_record_and_retrieve_learning(tmp_path) -> None:
    store = LearningStore(db_path=str(tmp_path / "learnings.db"))
    store.record_learning(
        LearningRecord(
            training_data_id="dataset-1",
            model_version="seq2neo-v1-staging",
            metrics={"auprc": 0.61},
            commit_hash="abc1234",
            timestamp="2026-03-15T12:00:00Z",
            notes="initial staging train",
            decision_rules=["rule-1"],
            top_features=["binding_affinity"],
            misclassifications=["pep-9"],
        )
    )

    summary = store.model_summary()
    assert len(summary["versions"]) == 1
    assert summary["versions"][0]["model_version"] == "seq2neo-v1-staging"


def test_suggest_retrain_based_on_label_delta(tmp_path) -> None:
    store = LearningStore(db_path=str(tmp_path / "learnings.db"))
    store.log_label_ingestion(total_count=30, accepted_count=25, flagged_count=5, high_uncertainty_count=10)
    result = store.suggest_retrain(label_delta_threshold=25)
    assert result["recommend_retrain"] is True
    assert result["target_stage"] == "staging"
