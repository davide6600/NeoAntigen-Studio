import json
import logging
import hashlib
from pathlib import Path
import requests

CACHE_DIR = Path("data/ensembl_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

def lookup_variant_gene(chrom: str, pos: int, ref: str, alt: str) -> str:
    """
    Cerca il gene overlapping per una variante genomica su Ensembl.
    Usato se VCF non ha campo GENE nel INFO field.
    """
    chrom_clean = chrom.replace("chr", "")
    cache_key = f"{chrom_clean}_{pos}_{ref}_{alt}"
    cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
    cache_file = CACHE_DIR / f"{cache_hash}.json"
    
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8")).get("gene", "UNKNOWN")
        except Exception:
            pass
            
    server = "https://rest.ensembl.org"
    ext = f"/overlap/region/human/{chrom_clean}:{pos}-{pos}?feature=gene"
    
    try:
        r = requests.get(server+ext, headers={ "Content-Type" : "application/json"}, timeout=5)
        r.raise_for_status()
        data = r.json()
        
        for item in data:
            if "external_name" in item:
                gene = item["external_name"]
                cache_file.write_text(json.dumps({"gene": gene}, indent=2), encoding="utf-8")
                return gene
                
        cache_file.write_text(json.dumps({"gene": "UNKNOWN"}, indent=2), encoding="utf-8")
        return "UNKNOWN"
        
    except Exception as e:
        logger.warning(f"Ensembl API failed for {chrom}:{pos}: {e}")
        return "UNKNOWN"
