import pytest
import re

from services.worker import hla_typing

VALID_ALLELES = ["HLA-A*02:01", "HLA-B*07:02", "HLA-C*07:01"]
INVALID_ALLELES = ["HLA-A*02:01", "INVALID", "A*02:01", "HLA-X*99"]


def test_validate_hla_format_keeps_valid():
    result = hla_typing.validate_hla_format(VALID_ALLELES)
    assert result == VALID_ALLELES


def test_validate_hla_format_removes_invalid():
    result = hla_typing.validate_hla_format(INVALID_ALLELES)
    assert "INVALID" not in result
    assert "A*02:01" not in result
    assert "HLA-A*02:01" in result


def test_resolve_hla_from_manifest():
    alleles, source = hla_typing.resolve_hla_alleles(
        manifest_hla=VALID_ALLELES
    )
    assert source == "manifest"
    assert alleles == VALID_ALLELES


def test_resolve_hla_default_when_empty():
    alleles, source = hla_typing.resolve_hla_alleles(manifest_hla=None)
    assert source == "default"
    assert len(alleles) > 0
    assert all(a.startswith("HLA-") for a in alleles)


def test_resolve_hla_manifest_filters_invalid():
    alleles, source = hla_typing.resolve_hla_alleles(
        manifest_hla=["HLA-A*02:01", "INVALID_FORMAT"]
    )
    assert source == "manifest"
    assert "INVALID_FORMAT" not in alleles


def test_optitype_available_returns_bool():
    result = hla_typing.optitype_available()
    assert isinstance(result, bool)


def test_build_candidate_peptides_uses_alleles(monkeypatch):
    from services.worker.phase2_predictors import build_candidate_peptides

    variants = [{"id": "v1", "gene": "TP53",
                 "alt_aa": "V", "ref_aa": "A", "position": 1}]
    candidates, hla_result = build_candidate_peptides(
        variants,
        hla_types=["HLA-A*02:01", "HLA-B*07:02"]
    )
    alleles_used = {c["hla_allele"] for c in candidates}
    assert "HLA-A*02:01" in alleles_used
    assert "HLA-B*07:02" in alleles_used
    assert hla_result.alleles == ["HLA-A*02:01", "HLA-B*07:02"]


def test_build_candidate_peptides_default_when_no_hla():
    from services.worker.phase2_predictors import build_candidate_peptides

    variants = [{"id": "v1", "gene": "TP53",
                 "alt_aa": "V", "ref_aa": "A", "position": 1}]
    candidates, hla_result = build_candidate_peptides(variants)
    assert len(candidates) > 0
    assert all("hla_allele" in c for c in candidates)
    assert len(hla_result.alleles) > 0


def test_stub_returns_valid_allele_format():
    result = hla_typing.type_hla(input_files=[], sample_id="stub-sample")
    pattern = re.compile(r"^HLA-[ABC]\*\d\d:\d\d$")
    assert all(pattern.match(allele) for allele in result.alleles)
    assert result.typing_method in {"stub_common_alleles", "stub"}


def test_result_has_required_fields():
    result = hla_typing.type_hla(input_files=[], sample_id="fields")
    assert hasattr(result, "alleles")
    assert hasattr(result, "typing_method")
    assert hasattr(result, "confidence")
    assert hasattr(result, "source_files")


@pytest.mark.skipif(
    hla_typing.optitype_available(),
    reason="optitype present"
)
def test_optitype_skipped_when_not_installed():
    result = hla_typing.type_hla(
        input_files=["reads_1.fastq", "reads_2.fastq"],
        sample_id="test",
        method="optitype",
    )
    assert result.typing_method in {"stub_common_alleles", "stub"}
    assert len(result.alleles) > 0


def test_empty_input_uses_stub():
    result = hla_typing.type_hla(input_files=[], sample_id="test")
    assert result.typing_method in {"stub_common_alleles", "stub"}


def test_resolve_from_manifest_with_alleles():
    result = hla_typing.resolve_hla_from_manifest(
        manifest={"hla_alleles": ["HLA-A*02:01", "HLA-B*07:02"]},
    )
    assert result.alleles == ["HLA-A*02:01", "HLA-B*07:02"]
    assert result.typing_method == "manifest_provided"


def test_resolve_from_manifest_legacy_hla_types():
    result = hla_typing.resolve_hla_from_manifest(
        manifest={"hla_types": ["HLA-A*02:01"]},
    )
    assert result.alleles == ["HLA-A*02:01"]
    assert "legacy" in result.typing_method


def test_resolve_from_manifest_empty_falls_to_stub():
    result = hla_typing.resolve_hla_from_manifest(
        manifest={},
        input_paths=[],
    )
    assert len(result.alleles) > 0
    assert result.typing_method == "stub_common_alleles"


def test_normalize_allele_format():
    assert hla_typing.normalize_allele_format("A*02:01") == "HLA-A*02:01"
    assert hla_typing.normalize_allele_format("HLA-A02:01") == "HLA-A*02:01"
    assert hla_typing.normalize_allele_format("hla-a*02:01") == "HLA-A*02:01"
    assert hla_typing.normalize_allele_format("INVALID") is None


def test_invalid_alleles_filtered_and_warned(caplog):
    import logging

    with caplog.at_level(logging.WARNING):
        result = hla_typing.resolve_hla_from_manifest(
            manifest={"hla_alleles": ["HLA-A*02:01", "INVALID_ALLELE"]},
        )
    assert "HLA-A*02:01" in result.alleles
    assert "INVALID_ALLELE" not in result.alleles
    assert any("INVALID_ALLELE" in r.message for r in caplog.records)
