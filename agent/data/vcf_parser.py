"""
Parser VCF minimale per varianti somatiche.
Supporta: VCF 4.1, 4.2 - solo SNV e INDEL somatici
"""
from typing import List, Dict, Optional
import os
import hashlib

def parse_vcf(vcf_path: str) -> List[Dict]:
    """
    Legge un file VCF e ritorna lista di varianti:
    {
        "chrom": str,
        "pos": int,
        "ref": str,
        "alt": str,
        "gene": str | None,
        "variant_type": "SNV" | "INDEL",
        "filter": str,  # PASS | altri
        "info": dict,
    }
    Solo varianti con FILTER=PASS vengono restituite.
    """
    if not os.path.isfile(vcf_path):
        raise FileNotFoundError(f"VCF file not found: {vcf_path}")
        
    variants = []
    
    with open(vcf_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
                
            parts = line.split("\t")
            if len(parts) < 8:
                continue
                
            chrom = parts[0]
            pos = int(parts[1])
            ref = parts[3]
            alt = parts[4]
            filter_val = parts[6]
            info_str = parts[7]
            
            if filter_val != "PASS":
                continue
                
            variant_type = "SNV" if len(ref) == 1 and len(alt) == 1 else "INDEL"
            
            info_dict = {}
            for item in info_str.split(";"):
                if "=" in item:
                    k, v = item.split("=", 1)
                    info_dict[k] = v
                else:
                    info_dict[item] = True
                    
            gene = info_dict.get("GENE")
            
            if not gene:
                from agent.data.ensembl_lookup import lookup_variant_gene
                gene = lookup_variant_gene(chrom, pos, ref, alt)
            
            variants.append({
                "chrom": chrom,
                "pos": pos,
                "ref": ref,
                "alt": alt,
                "gene": gene,
                "variant_type": variant_type,
                "filter": filter_val,
                "info": info_dict
            })
            
    return variants

def variants_to_peptides(
    variants: List[Dict],
    peptide_length: int = 9,
    flank_length: int = 4,
) -> List[str]:
    """
    Per ogni variante SNV, genera peptidi candidati di lunghezza
    peptide_length centrati sulla mutazione.
    Per ora usa sequenza aminoacidica mock basata sul codon change.
    Ritorna lista di peptidi unici.
    """
    peptides = set()
    aa_choices = "ACDEFGHIKLMNPQRSTVWY"
    
    for v in variants:
        if v["variant_type"] != "SNV":
            continue
            
        # Deterministic mock based on variant details
        h = hashlib.md5(f"{v['chrom']}:{v['pos']}:{v['ref']}:{v['alt']}".encode()).hexdigest()
        
        mutated_aa = aa_choices[int(h[0:2], 16) % 20]
        
        left = ""
        for i in range(flank_length):
            left += aa_choices[int(h[2+i:4+i], 16) % 20]
            
        right = ""
        for i in range(peptide_length - flank_length - 1):
            right += aa_choices[int(h[10+i:12+i], 16) % 20]
            
        pep = left + mutated_aa + right
        pep = pep[:peptide_length].ljust(peptide_length, 'A')
        peptides.add(pep)
        
    return list(peptides)
