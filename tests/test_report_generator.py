import pytest
from pathlib import Path
from agent.skills.report_generator import generate_report

def test_generate_report_markdown(tmp_path):
    job_id = "test-job"
    job_data = {
        "job_id": job_id,
        "metadata": {
            "patient_id": "PT-001",
            "peptides": ["SIINFEKL"]
        },
        "design": {
            "is_safe": True
        }
    }
    provenance = {
        "steps": [
            {"step": "vcf_parsing"},
            {"step": "immunogenicity_prediction", "predicted_binders": 1}
        ]
    }
    
    out_dir = tmp_path / "reports"
    out_file = generate_report(job_id, job_data, provenance, out_dir, "markdown")
    
    assert out_file.exists()
    assert out_file.name == f"{job_id}_report.md"
    
    content = out_file.read_text(encoding="utf-8")
    assert "PT-001" in content
    assert "**VCF File Parsed:** Yes" in content
    assert "**Predicted Binders:** 1" in content

def test_generate_report_html(tmp_path):
    job_data = {"job_id": "test", "metadata": {}}
    out_dir = tmp_path / "reports"
    out_file = generate_report("test", job_data, {}, out_dir, "html")
    
    assert out_file.exists()
    assert out_file.suffix == ".html"
    content = out_file.read_text(encoding="utf-8")
    assert "<html>" in content
    
def test_generate_report_pdf_fallback(tmp_path):
    job_data = {"job_id": "test", "metadata": {}}
    out_dir = tmp_path / "reports"
    # Even if reportlab is installed, it should succeed, so we just check it doesn't crash
    out_file = generate_report("test", job_data, {}, out_dir, "pdf")
    
    assert out_file.exists()
    assert out_file.suffix == ".pdf"
    content = out_file.read_bytes()
    assert content.startswith(b"%PDF-")
