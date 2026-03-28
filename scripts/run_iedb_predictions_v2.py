#!/usr/bin/env python3
"""
Run 150 peptides through IEDB API (NetMHCpan 4.1) - REAL PREDICTOR
Corrected API format based on IEDB documentation.
"""
import requests
import csv
import json
import sys
import time
from pathlib import Path

def predict_iedb_netmhcpan(peptide, allele):
    """
    Call IEDB NetMHCpan 4.1 API - REAL predictor.
    Uses the correct API format per IEDB documentation.
    """
    # Use the cluster interface directly
    url = 'https://tools-cluster-interface.iedb.org/tools_api/mhci/'
    
    # API requires specific format
    data = {
        'method': 'netmhcpan_ba',
        'sequence_text': peptide,
        'allele': allele,
        'length': len(peptide),
        'format': 'json',
    }
    
    headers = {
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, data=data, headers=headers, timeout=120, allow_redirects=True)
            
            if response.status_code == 406:
                # Try alternative format
                data_alt = {
                    'method': 'netmhcpan_ba',
                    'peptide': peptide,
                    'allele': allele,
                }
                response = requests.post(url, data=data_alt, headers=headers, timeout=120, allow_redirects=True)
            
            response.raise_for_status()
            result = response.json()
            
            if isinstance(result, list) and len(result) > 0:
                ic50 = float(result[0].get('ic50', 500.0))
                rank = float(result[0].get('percentile_rank', 50.0))
                return {
                    'ic50': ic50,
                    'rank': rank,
                    'binder': ic50 < 500,
                    'predictor': 'netmhcpan_iedb_api'
                }
            return None
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 406 and attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            print(f"HTTP Error {e.response.status_code}: {peptide}/{allele}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"Error predicting {peptide}/{allele}: {e}", file=sys.stderr)
            return None
    
    return None

def main():
    # Create output directory
    output_dir = Path('data/results')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    input_file = Path('data/input/real_peptides_150.csv')
    output_file = output_dir / 'iedb_netmhcpan_predictions.json'
    log_file = output_dir / 'iedb_predictions.log'
    
    if not input_file.exists():
        print(f"ERROR: Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)
    
    # Read peptides
    peptides = []
    with open(input_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            peptides.append({
                'peptide': row['peptide'],
                'hla_allele': row['hla_allele'],
                'source': row['source'],
                'immunogenic': int(row['immunogenic'])
            })
    
    print(f"Loaded {len(peptides)} peptides from {input_file}")
    print(f"Running NetMHCpan 4.1 predictions via IEDB API...")
    print("=" * 80)
    
    with open(log_file, 'w') as log:
        log.write(f"IEDB NetMHCpan 4.1 Predictions\n")
        log.write(f"Input: {len(peptides)} peptides\n\n")
        
        # Predict
        results = []
        for i, pep in enumerate(peptides, 1):
            pred = predict_iedb_netmhcpan(pep['peptide'], pep['hla_allele'])
            if pred:
                result = {
                    'peptide': pep['peptide'],
                    'hla_allele': pep['hla_allele'],
                    'source': pep['source'],
                    'immunogenic': pep['immunogenic'],
                    'ic50': pred['ic50'],
                    'rank': pred['rank'],
                    'binder': pred['binder'],
                    'predictor': pred['predictor']
                }
                results.append(result)
                
                # Progress
                status = "✓ BINDER" if pred['binder'] else "✗ non-binder"
                log_line = f"[{i:3d}/{len(peptides)}] {pep['peptide']:12s} / {pep['hla_allele']:12s} -> IC50: {pred['ic50']:8.2f} nM {status}"
                print(log_line)
                log.write(log_line + "\n")
            else:
                log_line = f"[{i:3d}/{len(peptides)}] {pep['peptide']:12s} / {pep['hla_allele']:12s} -> FAILED"
                print(log_line)
                log.write(log_line + "\n")
            
            # Rate limiting - be nice to the API
            if i % 10 == 0:
                time.sleep(1)
        
        # Save results
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Summary
        binders = sum(1 for r in results if r['binder'])
        non_binders = len(results) - binders
        failed = len(peptides) - len(results)
        
        summary = f"""
{'=' * 80}
PREDICTION SUMMARY
{'=' * 80}
Total peptides: {len(peptides)}
Successful predictions: {len(results)}
Failed: {failed}

Binders (IC50 < 500 nM): {binders}
Non-binders: {non_binders}

Results saved to: {output_file}
Log saved to: {log_file}
"""
        print(summary)
        log.write(summary)
        
        # Calculate metrics for known immunogenic peptides
        known_immunogenic = [r for r in results if r['immunogenic'] == 1]
        known_negative = [r for r in results if r['immunogenic'] == 0]
        
        if known_immunogenic:
            true_positives = sum(1 for r in known_immunogenic if r['binder'])
            sensitivity = true_positives / len(known_immunogenic)
            metrics = f"""
KNOWN IMMUNOGENIC PEPTIDES (n={len(known_immunogenic)}):
  True Positives: {true_positives}
  False Negatives: {len(known_immunogenic) - true_positives}
  Sensitivity: {sensitivity:.2%}
"""
            print(metrics)
            log.write(metrics)
        
        if known_negative:
            true_negatives = sum(1 for r in known_negative if not r['binder'])
            specificity = true_negatives / len(known_negative)
            metrics = f"""
KNOWN NEGATIVE PEPTIDES (n={len(known_negative)}):
  True Negatives: {true_negatives}
  False Positives: {len(known_negative) - true_negatives}
  Specificity: {specificity:.2%}
"""
            print(metrics)
            log.write(metrics)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
