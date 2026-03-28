import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

_SCHEMA_PATH = Path(__file__).parents[2] / "schemas" / "lims_manifest.json"
_CACHED_SCHEMA: dict | None = None

def _load_schema() -> dict:
    global _CACHED_SCHEMA
    if _CACHED_SCHEMA is None:
        if _SCHEMA_PATH.exists():
            _CACHED_SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        else:
            _CACHED_SCHEMA = {}
    return _CACHED_SCHEMA

def generate_assay_manifest(assay_type: str, candidate_peptides: list[dict]) -> dict:
    """Generate a LIMS manifest from a list of peptide candidates to be tested."""
    items = []
    for idx, candidate in enumerate(candidate_peptides):
        items.append({
            "sample_id": candidate.get("sample_id", "unknown_sample"),
            "peptide_id": candidate["peptide_id"],
            "well_position": f"A{idx+1}" # default simple well increment for illustration
        })
        
    manifest = {
        "manifest_id": f"LIMS-MNF-{str(uuid.uuid4()).split('-')[0]}",
        "created_at": datetime.now(UTC).isoformat(),
        "assay_type": assay_type,
        "items": items
    }
    return manifest

def parse_assay_manifest(raw_manifest: dict) -> list[dict]:
    """Parse a LIMS manifest into structured format."""
    return raw_manifest.get("items", [])
