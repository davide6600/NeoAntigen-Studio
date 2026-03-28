"""
Scarica e cachea binding data da IEDB REST API.
API docs: https://www.iedb.org/api_v2_doc.html
Endpoint: https://query-api.iedb.org/mhc_ligand_search
"""

import json
import logging
import time
import hashlib
from pathlib import Path
import requests

CACHE_DIR = Path("data/iedb_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

IEDB_API_PRIMARY = "https://query-api.iedb.org/mhc_ligand_search"
IEDB_API_LEGACY = "https://www.iedb.org/api/immune_epitope/export_csv/"


def fetch_mhc_binding_data(
    hla_allele: str = "HLA-A*02:01",
    peptide_length: int = 9,
    assay_type: str = "IC50",  # IC50 | percent_inhibition
    max_results: int = 500,
    use_cache: bool = True,
) -> list[dict]:
    """
    Ritorna lista di: {
        "peptide_sequence": str,
        "hla_allele": str,
        "measurement_value": float,
        "qualitative_measure": str,
        "is_binder": bool,
        "is_strong_binder": bool,
    }
    """
    cache_key = f"{hla_allele}_{peptide_length}_{assay_type}_{max_results}"
    cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
    cache_file = CACHE_DIR / f"{cache_hash}.json"

    if use_cache and cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Fetch da IEDB API
    results = []
    
    params = {
        "mhc_allele_name": hla_allele,
        "peptide_seq_length": peptide_length,
        "linear_peptide_seq": "",
        "assay_type_id": assay_type,
        "offset": 0,
        "limit": max_results,
    }
    
    try:
        # Try primary endpoint
        resp = requests.get(IEDB_API_PRIMARY, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        # parse primary endpoint format
        # assume response has data array
        for item in data.get("data", []):
            seq = item.get("linear_peptide_seq") or item.get("peptide_seq")
            val = item.get("measurement_value")
            
            if seq and val is not None:
                val = float(val)
                is_binder = val < 500.0
                is_strong = val < 50.0
                results.append({
                    "peptide_sequence": seq,
                    "hla_allele": hla_allele,
                    "measurement_value": val,
                    "qualitative_measure": item.get("qualitative_measure", "Unknown"),
                    "is_binder": is_binder,
                    "is_strong_binder": is_strong,
                })
                
        if not results:
            raise ValueError("Empty data array in primary IEDB response")

    except Exception as e_primary:
        logger.warning(f"Primary IEDB API failed: {e_primary}. Falling back to legacy endpoint.")
        try:
            # Fallback to legacy endpoint
            payload = {
                "mhc_allele_name": hla_allele,
                "peptide_seq_length": peptide_length,
                "assay_type": assay_type,
                "limit": max_results
            }
            resp_legacy = requests.post(
                IEDB_API_LEGACY, 
                json=payload, 
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            resp_legacy.raise_for_status()
            
            if "application/json" in resp_legacy.headers.get("Content-Type", ""):
                data = resp_legacy.json()
            else:
                data = {"data": []}  # Mock empty if CSV or unsupported
                
            for item in data.get("data", []):
                seq = item.get("peptide_sequence") or item.get("linear_peptide_seq", "")
                val = item.get("measurement_value", 5000)
                val = float(val)
                results.append({
                    "peptide_sequence": seq,
                    "hla_allele": hla_allele,
                    "measurement_value": val,
                    "qualitative_measure": item.get("qualitative_measure", "Unknown"),
                    "is_binder": val < 500.0,
                    "is_strong_binder": val < 50.0,
                })
                
        except Exception as e_legacy:
            logger.warning(f"Legacy IEDB API failed: {e_legacy}. Offline fallback will be used.")
            return []

    if results and use_cache:
        cache_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
        
    return results

def build_sklearn_model_from_iedb(
    hla_alleles: list[str] = ["HLA-A*02:01", "HLA-B*07:02"],
    cache_only: bool = False,
) -> dict:
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    import joblib
    
    # Feature extractor
    def _extract_features(peptide: str) -> list[float]:
        kd_scale = {
            'A': 1.8, 'R': -4.5, 'N': -3.5, 'D': -3.5, 'C': 2.5,
            'Q': -3.5, 'E': -3.5, 'G': -0.4, 'H': -3.2, 'I': 4.5,
            'L': 3.8, 'K': -3.9, 'M': 1.9, 'F': 2.8, 'P': -1.6,
            'S': -0.8, 'T': -0.7, 'W': -0.9, 'Y': -1.3, 'V': 4.2
        }
        hydro = sum(kd_scale.get(c.upper(), 0.0) for c in peptide) / max(len(peptide), 1)
        anchor_2 = 1.0 if len(peptide) > 1 and peptide[1].upper() in ('L', 'M') else 0.0
        anchor_c = 1.0 if len(peptide) > 0 and peptide[-1].upper() in ('V', 'L') else 0.0
        return [hydro, anchor_2, anchor_c, len(peptide)]

    X = []
    y = []
    
    peptides_used = 0
    
    for hla in hla_alleles:
        data = fetch_mhc_binding_data(hla_allele=hla, max_results=200, use_cache=True)
        if not data and not cache_only:
             data = fetch_mhc_binding_data(hla_allele=hla, max_results=200, use_cache=False)
             
        for item in data:
            seq = item["peptide_sequence"]
            if len(seq) < 8:
                 continue
            X.append(_extract_features(seq))
            y.append(1 if item["is_binder"] else 0)
            peptides_used += 1

    if peptides_used < 10:
        return {"model_path": None, "n_samples": 0, "accuracy": 0.0, "alleles": hla_alleles}
        
    clf = RandomForestClassifier(n_estimators=10, random_state=42)
    clf.fit(X, y)
    
    models_dir = Path("data/models")
    models_dir.mkdir(parents=True, exist_ok=True)
    
    model_hash = hashlib.md5("".join(hla_alleles).encode()).hexdigest()
    model_path = models_dir / f"immunogenicity_rf_{model_hash}.pkl"
    joblib.dump(clf, model_path)
    
    acc = float(clf.score(X, y)) if len(set(y)) > 1 else 1.0
    
    return {
        "model_path": str(model_path),
        "n_samples": peptides_used,
        "accuracy": acc,
        "alleles": hla_alleles,
        "clf": clf  # returning instance for seamless runtime usage
    }
