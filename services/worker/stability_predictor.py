"""
MHC-I peptide-complex stability prediction.
Backends: NetMHCstabpan (local) -> IEDB stability API -> formula stub.
"""
from __future__ import annotations

import hashlib, logging, math
import urllib.parse, urllib.request, json

logger = logging.getLogger(__name__)
VALID_STABILITY_BACKENDS = frozenset([
    "netmhcstabpan_local",
    "netmhcstabpan_iedb_api",
    "stability_stub",
])


def predict_stability_iedb(peptide: str, allele: str) -> dict | None:
    """
    IEDB stability API (NetMHCstabpan via REST).
    Endpoint: https://tools.iedb.org/tools_api/stability/
    Restituisce None se la chiamata fallisce.
    """
    url = "https://tools.iedb.org/tools_api/stability/"
    data = urllib.parse.urlencode({
        "sequence_text": peptide,
        "allele": allele,
        "output_format": "json",
    }).encode()
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
        thalf = float(result.get("thalf", 1.0))
        score = float(result.get("score_predicted", _thalf_to_score(thalf)))
        return {
            "stability_score": round(score, 4),
            "thalf_hours": round(thalf, 3),
            "stability_backend": "netmhcstabpan_iedb_api",
        }
    except Exception as e:
        logger.warning("IEDB stability API failed: %s", e)
        return None


def _thalf_to_score(thalf_hours: float) -> float:
    """t1/2 -> score 0-1. t1/2=0.5h->0.0, t1/2=2h->0.5, t1/2=8h->1.0."""
    log_min, log_max = math.log10(0.5), math.log10(8.0)
    raw = (math.log10(max(thalf_hours, 0.01)) - log_min) / (log_max - log_min)
    return round(max(0.0, min(1.0, raw)), 4)


def _stability_stub(peptide: str, allele: str) -> dict:
    digest = hashlib.sha256(f"stab|{peptide}|{allele}".encode()).hexdigest()
    score = round(0.3 + (int(digest[:8], 16) / 0xFFFFFFFF * 0.5), 4)
    return {
        "stability_score": score,
        "thalf_hours": None,
        "stability_backend": "stability_stub",
    }


def predict_stability(peptide: str, allele: str) -> dict:
    """
    Cascata: IEDB stability API -> stub.
    (NetMHCstabpan locale aggiunto come opzione futura ma non implementato qui)
    """
    result = predict_stability_iedb(peptide, allele)
    if result is not None:
        return result
    return _stability_stub(peptide, allele)


def get_available_stability_backend() -> str:
    try:
        req = urllib.request.Request(
            "https://tools.iedb.org/tools_api/stability/",
            data=b"ping=1", method="POST")
        urllib.request.urlopen(req, timeout=5)
        return "netmhcstabpan_iedb_api"
    except Exception:
        return "stability_stub"
