"""
Real MHC-I binding predictors for NeoAntigen-Studio.
Cascade: MHCflurry 2.0 -> IEDB REST API -> stub fallback.
"""
from __future__ import annotations
import hashlib, logging, math
import urllib.error, urllib.parse, urllib.request, json

logger = logging.getLogger(__name__)
VALID_PREDICTORS = frozenset([
    "mhcflurry_2", "netmhcpan_iedb_api", "stub_fallback", "pvacseq"
])


class MHCflurryNotAvailableError(RuntimeError):
    pass


def _normalize_allele(allele: str) -> str:
    return allele.replace("*", "")


def _ic50_to_score(ic50_nm: float) -> float:
    log_min, log_max = math.log10(50.0), math.log10(50_000.0)
    raw = 1.0 - (math.log10(max(ic50_nm, 1.0)) - log_min) / (log_max - log_min)
    return round(max(0.0, min(1.0, raw)), 4)


def predict_binding_mhcflurry(peptide: str, allele: str) -> dict:
    try:
        from mhcflurry import Class1PresentationPredictor
    except ImportError as e:
        raise MHCflurryNotAvailableError(str(e)) from e
    try:
        p = Class1PresentationPredictor.load()
        result = p.predict(
            peptides=[peptide],
            alleles=[_normalize_allele(allele)],
            include_affinity_percentile=True,
        )
        row = result.iloc[0]
        aff = float(row.get("mhcflurry_affinity", 500.0))
        pct = float(row.get("mhcflurry_affinity_percentile", 50.0))
        return {"score": _ic50_to_score(aff), "affinity_nm": round(aff, 2),
                "percentile_rank": round(pct, 2), "predictor": "mhcflurry_2"}
    except Exception as e:
        raise MHCflurryNotAvailableError(str(e)) from e


def predict_binding_iedb_api(peptide: str, allele: str) -> dict | None:
    url = "https://tools.iedb.org/tools_api/mhci/"
    data = urllib.parse.urlencode({
        "method": "netmhcpan_ba", "sequence_text": peptide,
        "allele": allele, "length": str(len(peptide)), "output_format": "json",
    }).encode()
    try:
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (compatible; NeoAntiGen-Studio/1.0)",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
        ic50 = float(result[0].get("ic50", 500.0))
        pct = float(result[0].get("percentile_rank", 50.0))
        return {"score": _ic50_to_score(ic50), "affinity_nm": round(ic50, 2),
                "percentile_rank": round(pct, 2), "predictor": "netmhcpan_iedb_api"}
    except Exception as e:
        logger.warning("IEDB API failed: %s", e)
        return None


def _stub_fallback(peptide: str, allele: str) -> dict:
    digest = hashlib.sha256(f"{peptide}|{allele}".encode()).hexdigest()
    score = round(0.35 + (int(digest[:8], 16) / 0xFFFFFFFF * 0.6), 4)
    return {"score": score, "affinity_nm": None,
            "percentile_rank": None, "predictor": "stub_fallback"}


def predict_binding(
    peptide: str,
    allele: str,
    prefer_offline: bool = True,
    backend: str = "auto",
) -> dict:
    if backend == "stub":
        return _stub_fallback(peptide, allele)

    if backend == "pvacseq":
        try:
            from . import pvacseq_backend

            result = pvacseq_backend.predict_binding_pvacseq(peptide, allele)
            if result is not None:
                return result
        except ImportError:
            pass
        logger.warning("pVACseq not available, falling back to stub")
        return _stub_fallback(peptide, allele)

    if backend == "iedb":
        result = predict_binding_iedb_api(peptide, allele)
        return result if result is not None else _stub_fallback(peptide, allele)

    if backend == "mhcflurry":
        try:
            return predict_binding_mhcflurry(peptide, allele)
        except MHCflurryNotAvailableError:
            return _stub_fallback(peptide, allele)

    if prefer_offline:
        try:
            return predict_binding_mhcflurry(peptide, allele)
        except MHCflurryNotAvailableError:
            pass
    result = predict_binding_iedb_api(peptide, allele)
    if result is not None:
        return result
    logger.warning("All real predictors failed, using stub_fallback")
    return _stub_fallback(peptide, allele)


def get_available_predictor() -> str:
    try:
        from mhcflurry import Class1PresentationPredictor
        Class1PresentationPredictor.load()
        return "mhcflurry_2"
    except Exception:
        pass
    try:
        urllib.request.urlopen(
            urllib.request.Request(
                "https://tools.iedb.org/tools_api/mhci/",
                data=b"ping=1", method="POST"),
            timeout=5)
        return "netmhcpan_iedb_api"
    except Exception:
        pass
    return "stub_fallback"
