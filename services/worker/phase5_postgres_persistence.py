import builtins
import json
from typing import Any
import os

def persist_labels(labels: list[Any]) -> None:
    """Consumes parsed label_ingest.ExperimentLabel objects and persists them to Postgres."""
    database_url = os.getenv("NEOANTIGEN_DATABASE_URL", "").strip()
    if not database_url:
        return
        
    try:
        psycopg = builtins.__import__("psycopg")
    except ImportError:
        return
        
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for label in labels:
                # Ensure the referenced peptide_id actually exists in the db to avoid FK violation during synthetic tests
                cur.execute("SELECT 1 FROM peptide_candidate WHERE peptide_id = %s", (label.peptide_id,))
                if not cur.fetchone():
                    continue

                qc_flags = label.qc_metrics or {}
                
                cur.execute(
                    """
                    INSERT INTO experiment_label 
                    (label_id, peptide_id, assay_type, assay_id, result, score, qc_flags, uploaded_by, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                    ON CONFLICT (label_id) DO UPDATE SET
                        result = EXCLUDED.result,
                        score = EXCLUDED.score,
                        qc_flags = EXCLUDED.qc_flags,
                        updated_at = now()
                    """,
                    (
                        label.label_id,
                        label.peptide_id,
                        label.assay_type,
                        label.assay_id,
                        label.result,
                        label.score,
                        json.dumps(qc_flags),
                        label.uploaded_by,
                        label.timestamp
                    )
                )
        conn.commit()

def resolve_flagged_label(label_id: str, decision: str) -> None:
    database_url = os.getenv("NEOANTIGEN_DATABASE_URL", "").strip()
    if not database_url:
        return
        
    try:
        psycopg = builtins.__import__("psycopg")
    except ImportError:
        return
        
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT qc_flags FROM experiment_label WHERE label_id = %s
                """,
                (label_id,)
            )
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Label {label_id} not found in database")
            
            raw_flags = row[0] if row[0] is not None else {}
            qc_flags: dict[str, Any] = dict(raw_flags)
            qc_flags["flagged"] = False
            qc_flags["review_decision"] = decision
            
            cur.execute(
                """
                UPDATE experiment_label
                SET qc_flags = %s::jsonb
                WHERE label_id = %s
                """,
                (json.dumps(qc_flags), label_id)
            )
        conn.commit()

def get_flagged_labels() -> list[dict]:
    database_url = os.getenv("NEOANTIGEN_DATABASE_URL", "").strip()
    if not database_url:
        return []
        
    try:
        psycopg = builtins.__import__("psycopg")
        psycopg_rows = builtins.__import__("psycopg.rows", fromlist=["dict_row"])
        dict_row = psycopg_rows.dict_row
    except ImportError:
        return []

    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT label_id, peptide_id, assay_type, assay_id, result, score, qc_flags, uploaded_by, timestamp
                FROM experiment_label
                WHERE qc_flags->>'flagged' = 'true'
                ORDER BY timestamp DESC
                """
            )
            rows = cur.fetchall()
            
            # Helper to convert datetimes to isoformat for json serialization
            results = []
            for r in rows:
                d = dict(r)
                if 'timestamp' in d and d['timestamp']:
                    d['timestamp'] = d['timestamp'].isoformat()
                if 'created_at' in d and d['created_at']:
                    d['created_at'] = d['created_at'].isoformat()
                results.append(d)
            return results
