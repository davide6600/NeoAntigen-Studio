from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
import shutil
import subprocess
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TCRRecognitionResult:
    score: float
    rank_percentile: float | None
    method: str
    raw_output: dict


def _prime2_available() -> bool:
    try:
        import PRIME  # type: ignore  # noqa: F401
        return True
    except Exception:
        pass
    return shutil.which("prime2") is not None


def _predict_prime2(peptide: str, allele: str) -> TCRRecognitionResult | None:
    try:
        from PRIME import predict_immunogenicity  # type: ignore

        result = predict_immunogenicity(peptide, allele)
        if isinstance(result, dict):
            score = float(result.get("score", result.get("immunogenicity_score", 0.5)))
            rank = result.get("rank_percentile")
            return TCRRecognitionResult(
                score=max(0.0, min(1.0, score)),
                rank_percentile=float(rank) if rank is not None else None,
                method="prime2",
                raw_output=result,
            )
        score = float(result)
        return TCRRecognitionResult(
            score=max(0.0, min(1.0, score)),
            rank_percentile=None,
            method="prime2",
            raw_output={"score": score},
        )
    except Exception:
        pass

    if shutil.which("prime2") is None:
        return None

    try:
        result = subprocess.run(
            ["prime2", "--peptide", peptide, "--allele", allele, "--output", "json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        payload = json.loads(result.stdout.strip() or "{}")
        score = float(payload.get("score", payload.get("immunogenicity_score", 0.5)))
        rank = payload.get("rank_percentile")
        return TCRRecognitionResult(
            score=max(0.0, min(1.0, score)),
            rank_percentile=float(rank) if rank is not None else None,
            method="prime2",
            raw_output=payload,
        )
    except Exception:
        return None


def _predict_iedb_immunogenicity(peptide: str, allele: str) -> TCRRecognitionResult | None:
    url = "https://tools.iedb.org/tools_api/immunogenicity/"
    data = urllib.parse.urlencode({
        "sequence_text": peptide,
        "mhc_allele": allele,
        "output_format": "json",
    }).encode()
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode())

        if isinstance(payload, list):
            payload = payload[0] if payload else {}
        score = float(payload.get("score", payload.get("immunogenicity_score", 0.5)))
        rank = payload.get("rank_percentile")
        normalized = max(0.0, min(1.0, score))
        return TCRRecognitionResult(
            score=normalized,
            rank_percentile=float(rank) if rank is not None else None,
            method="iedb_immunogenicity",
            raw_output=payload if isinstance(payload, dict) else {"payload": payload},
        )
    except Exception as e:
        logger.warning("IEDB immunogenicity API failed: %s", e)
        return None


def _stub_tcr(peptide: str, allele: str) -> TCRRecognitionResult:
    digest = hashlib.sha256(f"{peptide}|tcr|{allele}".encode()).hexdigest()
    fraction = int(digest[:8], 16) / 0xFFFFFFFF
    score = round(0.25 + (fraction * 0.6), 4)
    logger.warning("TCR recognition score is simulated")
    return TCRRecognitionResult(
        score=score,
        rank_percentile=None,
        method="stub_tcr",
        raw_output={"score": score, "simulated": True},
    )


def predict_tcr_recognition(
    peptide: str,
    allele: str,
    method: str = "auto",
) -> TCRRecognitionResult:
    method = method.lower().strip()

    if method == "stub":
        return _stub_tcr(peptide, allele)

    if method in {"auto", "prime2"} and _prime2_available():
        result = _predict_prime2(peptide, allele)
        if result is not None:
            return result
        if method == "prime2":
            return _stub_tcr(peptide, allele)

    if method in {"auto", "iedb_immunogenicity"}:
        result = _predict_iedb_immunogenicity(peptide, allele)
        if result is not None:
            return result

    return _stub_tcr(peptide, allele)


def get_available_tcr_predictor() -> str:
    if _prime2_available():
        return "prime2"
    try:
        req = urllib.request.Request(
            "https://tools.iedb.org/tools_api/immunogenicity/",
            data=b"ping=1", method="POST"
        )
        urllib.request.urlopen(req, timeout=5)
        return "iedb_immunogenicity"
    except Exception:
        return "stub_tcr"
