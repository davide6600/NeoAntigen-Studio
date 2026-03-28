import os
import pytest
from agent.data.vcf_parser import parse_vcf, variants_to_peptides

def test_parse_vcf_success():
    vcf_path = "pipelines/nextflow/neoantigen_pipeline/test_data/sample.vcf"
    
    if not os.path.exists(vcf_path):
        pytest.skip(f"Test VCF not found at {vcf_path}")
        
    variants = parse_vcf(vcf_path)
    
    # 12 variants in total, 2 REJECT, so 10 PASS
    assert len(variants) == 10
    
    # Check gene annotations
    tp53 = [v for v in variants if v["gene"] == "TP53"]
    assert len(tp53) == 3
    
    kras = [v for v in variants if v["gene"] == "KRAS"]
    assert len(kras) == 2
    
    # Verify filter logic
    assert all(v["filter"] == "PASS" for v in variants)
    
def test_parse_vcf_not_found():
    with pytest.raises(FileNotFoundError):
        parse_vcf("non_existent_file.vcf")

def test_variants_to_peptides():
    variants = [
        {"chrom": "chr1", "pos": 100, "ref": "A", "alt": "T", "variant_type": "SNV"},
        {"chrom": "chr1", "pos": 200, "ref": "C", "alt": "G", "variant_type": "SNV"}
    ]
    
    peptides = variants_to_peptides(variants, peptide_length=9, flank_length=4)
    
    assert len(peptides) == 2
    for p in peptides:
        assert len(p) == 9
        assert all(c in "ACDEFGHIKLMNPQRSTVWY" for c in p)
        
def test_variants_to_peptides_indels_ignored():
    variants = [
        {"chrom": "chr1", "pos": 100, "ref": "A", "alt": "T", "variant_type": "SNV"},
        {"chrom": "chr1", "pos": 101, "ref": "AC", "alt": "T", "variant_type": "INDEL"}
    ]
    
    peptides = variants_to_peptides(variants)
    
    # Only the SNV should be processed
    assert len(peptides) == 1
