import os
import json
from pathlib import Path
from datetime import datetime, UTC
import logging

logger = logging.getLogger(__name__)

def _generate_markdown(job_data: dict, provenance: dict) -> str:
    """Generates a Markdown report string."""
    job_id = job_data.get("job_id", "Unknown")
    patient_id = job_data.get("metadata", {}).get("patient_id", "Unknown")
    peptides = job_data.get("metadata", {}).get("peptides", [])
    run_mode = job_data.get("run_mode", "dry_run")
    
    # Safe findings
    design = job_data.get("design", {})
    is_safe = design.get("is_safe", False)
    findings = design.get("safety_findings", [])
    
    # Audit trail extraction
    vcf_step = next((s for s in provenance.get("steps", []) if s.get("step") == "vcf_parsing"), None)
    imm_step = next((s for s in provenance.get("steps", []) if s.get("step") == "immunogenicity_prediction"), None)
    
    md = f"# NeoAntigen-Studio Scientific Report\n"
    md += f"**Job ID:** {job_id}\n"
    md += f"**Patient ID:** {patient_id}\n"
    md += f"**Date:** {datetime.now(UTC).isoformat()}\n"
    md += f"**Run Mode:** {run_mode}\n\n"
    
    md += f"## ⚠️ RUO Disclaimer\n"
    md += f"> For Research Use Only. Not for use in diagnostic procedures.\n\n"
    
    md += f"## Input Data\n"
    md += f"- **Base Peptides Provided:** {len(peptides)}\n"
    if vcf_step:
        md += f"- **VCF File Parsed:** Yes\n"
    
    md += f"## Immunogenicity Predictions\n"
    if imm_step:
        md += f"- **Predictor Used:** {imm_step.get('predictor', 'sklearn')}\n"
        md += f"- **Predicted Binders:** {imm_step.get('predicted_binders', 0)}\n"
    else:
        md += f"- *Data not available or skipped.*\n"
        
    md += f"## mRNA Design & Safety\n"
    md += f"- **Safety Passed:** {'✅ Yes' if is_safe else '❌ No'}\n"
    if findings:
        md += f"- **Findings:** {', '.join(findings)}\n"
        
    md += f"## Provenance & Traceability\n"
    md += f"- **Pipeline Version:** {provenance.get('pipeline_version', 'Unknown')}\n"
    md += f"- **Model Version:** {provenance.get('model_version', 'Unknown')}\n"
    
    return md


def generate_report(job_id: str, job_data: dict, provenance: dict, output_dir: Path, output_format: str = "markdown") -> Path:
    """
    Generates a scientific report.
    output_format: "markdown", "html", or "pdf"
    Returns the path to the generated report file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    md_content = _generate_markdown(job_data, provenance)
    
    if output_format == "markdown":
        out_file = output_dir / f"{job_id}_report.md"
        out_file.write_text(md_content, encoding="utf-8")
        return out_file
        
    elif output_format == "html":
        # Simple HTML wrapper
        html_content = f"<html><head><title>Report {job_id}</title><meta charset='utf-8'></head><body>"
        html_content += md_content.replace("\n", "<br>").replace("## ", "<h2>").replace("# ", "<h1>")
        html_content += "</body></html>"
        
        out_file = output_dir / f"{job_id}_report.html"
        out_file.write_text(html_content, encoding="utf-8")
        return out_file
        
    elif output_format == "pdf":
        out_file = output_dir / f"{job_id}_report.pdf"
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            from reportlab.lib.utils import simpleSplit
            
            c = canvas.Canvas(str(out_file), pagesize=letter)
            width, height = letter
            y = height - 50
            
            for line in md_content.split("\n"):
                if y < 50:
                    c.showPage()
                    y = height - 50
                # Very basic wrap
                wrapped_lines = simpleSplit(line, "Helvetica", 12, width - 100)
                for wline in wrapped_lines:
                    c.drawString(50, y, wline)
                    y -= 15
                y -= 5
            c.save()
            return out_file
            
        except ImportError:
            logger.warning("reportlab not installed, falling back to markdown PDF mock")
            # Fallback for environments lacking reportlab (e.g. testing)
            out_file.write_bytes(b"%PDF-1.4\n" + md_content.encode("utf-8"))
            return out_file
            
    else:
        raise ValueError(f"Unsupported report format: {output_format}")
