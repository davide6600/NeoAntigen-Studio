import datetime
from pathlib import Path
import json

def generate_job_report_pdf(job_id: str, pipeline_result: dict, output_dir: str = "data/reports") -> Path:
    target = Path(output_dir) / f"{job_id}.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    
    # Extract dynamic, real data
    engine = pipeline_result.get("engine", "Unknown")
    outputs = pipeline_result.get("outputs", {})
    
    # Try to load top candidate
    top_peptide = "None"
    top_score = "0.000"
    total_variants = 0
    
    ranked_path = outputs.get("ranked_peptides_json")
    if ranked_path and Path(ranked_path).exists():
        with open(ranked_path, "r") as f:
            ranked_data = json.load(f)
            total_variants = len(ranked_data)
            if ranked_data:
                top_peptide = str(ranked_data[0].get("peptide", "N/A"))
                top_score = str(ranked_data[0].get("final_score", "0.000"))

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # We will compute lengths and offsets automatically to make a valid PDF
    lines = [
        f"NeoAntigen-Studio RUO Report",
        f"----------------------------",
        f"Job ID: {job_id}",
        f"Date: {now}",
        f"Engine: {engine}",
        f"Total Candidates Supported: {total_variants}",
        f"Top Candidate: {top_peptide}",
        f"Top Sequence Score: {top_score}",
        f"",
        f"End of Report."
    ]
    
    # PDF generation logic
    content_stream = b"BT /F1 12 Tf\n"
    y = 750
    for line in lines:
        cleaned_line = line.replace('(', '\\(').replace(')', '\\)')
        content_stream += f"20 {y} Td ({cleaned_line}) Tj\n0 -16 Td\n".encode('ascii')
        y -= 20
    content_stream += b"ET"
    
    stream_len = len(content_stream)
    
    obj_1 = b"1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n"
    obj_2 = b"2 0 obj\n<</Type/Pages/Count 1/Kids[3 0 R]>>\nendobj\n"
    obj_3 = b"3 0 obj\n<</Type/Page/Parent 2 0 R/MediaBox[0 0 600 800]/Contents 4 0 R/Resources<</Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Helvetica>> >> >> >>\nendobj\n"
    obj_4 = f"4 0 obj\n<</Length {stream_len}>>\nstream\n".encode('ascii') + content_stream + b"\nendstream\nendobj\n"
    
    header = b"%PDF-1.4\n"
    body = header + obj_1 + obj_2 + obj_3 + obj_4
    
    # Xref calculation
    xref = b"xref\n0 5\n"
    xref += b"0000000000 65535 f \n"
    
    offset = len(header)
    xref += f"{offset:010d} 00000 n \n".encode('ascii')
    offset += len(obj_1)
    xref += f"{offset:010d} 00000 n \n".encode('ascii')
    offset += len(obj_2)
    xref += f"{offset:010d} 00000 n \n".encode('ascii')
    offset += len(obj_3)
    xref += f"{offset:010d} 00000 n \n".encode('ascii')
    offset += len(obj_4)
    
    trailer = b"trailer\n<</Size 5/Root 1 0 R>>\nstartxref\n"
    trailer += str(offset).encode('ascii') + b"\n%%EOF\n"
    
    pdf_bytes = body + xref + trailer
    target.write_bytes(pdf_bytes)
    return target
