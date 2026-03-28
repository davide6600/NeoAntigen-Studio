from __future__ import annotations

import json

from services.worker.cohort_analysis import (
    analyze_cohort,
    export_cohort_csv,
    hla_frequency_table,
    hla_heatmap_data,
    shared_peptides,
)


def _write_ranked(path, rows):
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return path


def _cohort_files(tmp_path):
    patient_1 = _write_ranked(
        tmp_path / "patient_1_ranked_peptides.json",
        [
            {
                "peptide": "GILGFVFTL",
                "hla_allele": "HLA-A*02:01",
                "binding_score": 0.82,
                "final_score": 0.91,
                "predictor_used": "mhcflurry_2",
                "scores_are_partial": False,
                "tcr_score": 0.74,
                "tcr_method": "iedb_immunogenicity",
            },
            {
                "peptide": "LLGATCMFV",
                "hla_allele": "HLA-B*07:02",
                "binding_score": 0.67,
                "final_score": 0.71,
                "predictor_used": "mhcflurry_2",
                "scores_are_partial": True,
                "tcr_score": 0.41,
                "tcr_method": "stub_tcr",
            },
        ],
    )
    patient_2 = _write_ranked(
        tmp_path / "patient_2_ranked_peptides.json",
        [
            {
                "peptide": "GILGFVFTL",
                "hla_allele": "HLA-A*02:01",
                "binding_score": 0.79,
                "final_score": 0.88,
                "predictor_used": "netmhcpan_iedb_api",
                "scores_are_partial": False,
                "tcr_score": 0.69,
                "tcr_method": "iedb_immunogenicity",
            },
            {
                "peptide": "SLYNTVATL",
                "hla_allele": "HLA-C*07:01",
                "binding_score": 0.72,
                "final_score": 0.77,
                "predictor_used": "stub_fallback",
                "scores_are_partial": True,
                "tcr_score": 0.37,
                "tcr_method": "stub_tcr",
            },
        ],
    )
    patient_3 = _write_ranked(
        tmp_path / "patient_3_ranked_peptides.json",
        [
            {
                "peptide": "NLVPMVATV",
                "hla_allele": "HLA-A*02:01",
                "binding_score": 0.75,
                "final_score": 0.8,
                "predictor_used": "pvacseq",
                "scores_are_partial": False,
                "tcr_score": 0.63,
                "tcr_method": "prime2",
            },
            {
                "peptide": "KLGGALQAK",
                "hla_allele": "HLA-B*07:02",
                "binding_score": 0.61,
                "final_score": 0.66,
                "predictor_used": "mhcflurry_2",
                "scores_are_partial": False,
                "tcr_score": 0.44,
                "tcr_method": "iedb_immunogenicity",
            },
        ],
    )
    return [patient_1, patient_2, patient_3]


def test_analyze_cohort_basic(tmp_path):
    files = _cohort_files(tmp_path)
    summary = analyze_cohort(files, patient_ids=["p1", "p2", "p3"])

    assert summary.n_patients == 3
    assert summary.n_peptides_total == 6
    assert summary.n_unique_peptides == 5
    assert isinstance(summary.median_binding_score, float)
    assert isinstance(summary.median_final_score, float)
    assert len(summary.per_patient_stats) == 3


def test_shared_peptides_found(tmp_path):
    files = _cohort_files(tmp_path)
    shared = shared_peptides(files, min_patients=2, min_final_score=0.5)

    assert any(item["peptide"] == "GILGFVFTL" for item in shared)


def test_hla_frequency_sums_correctly(tmp_path):
    files = _cohort_files(tmp_path)
    freq = hla_frequency_table(files)

    assert round(sum(freq.values()), 6) == 1.0


def test_heatmap_data_shape(tmp_path):
    files = _cohort_files(tmp_path)
    heatmap = hla_heatmap_data(files)

    assert len(heatmap["matrix"]) == len(heatmap["patients"]) == 3
    assert len(heatmap["matrix"][0]) == len(heatmap["alleles"])
    assert all(cell in (0, 1) for row in heatmap["matrix"] for cell in row)


def test_export_csv_creates_file(tmp_path):
    files = _cohort_files(tmp_path)
    summary = analyze_cohort(files, patient_ids=["p1", "p2", "p3"])
    output_path = tmp_path / "cohort.csv"

    export_cohort_csv(summary, output_path)

    assert output_path.exists()
    header = output_path.read_text(encoding="utf-8").splitlines()[0]
    assert "patient_id" in header
