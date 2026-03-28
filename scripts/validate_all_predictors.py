#!/usr/bin/env python3
"""
Validate all predictors are working before full run.
"""
import sys
import csv

def test_mhcflurry():
    """Test MHCflurry with known peptides."""
    print("=" * 60)
    print("Testing MHCflurry 2.1.0...")
    print("=" * 60)
    
    try:
        import mhcflurry
        print(f"✓ MHCflurry version: {mhcflurry.__version__}")
        
        # Load predictor
        predictor = mhcflurry.Class1AffinityModel.load()
        print("✓ Model loaded successfully")
        
        # Test peptides
        test_peptides = [
            ("GILGFVFTL", "HLA-A*02:01"),  # Flu M1 - known binder
            ("NLVPMVATV", "HLA-A*02:01"),  # CMV pp65 - known binder
            ("SIINFEKL", "HLA-A*02:01"),   # OVA - known binder
            ("AAAAAAAAA", "HLA-A*02:01"),  # Negative control
        ]
        
        print("\nPredictions:")
        for peptide, allele in test_peptides:
            result = predictor.predict(peptide=peptide, alleles=[allele])
            ic50 = result[0]
            binder = "✓ BINDER" if ic50 < 500 else "✗ non-binder"
            print(f"  {peptide:12s} / {allele:12s} -> IC50: {ic50:8.2f} nM {binder}")
        
        return True
        
    except Exception as e:
        print(f"✗ MHCflurry test FAILED: {e}")
        return False


def test_dataset():
    """Test that dataset is valid."""
    print("\n" + "=" * 60)
    print("Validating peptide dataset...")
    print("=" * 60)
    
    try:
        with open("data/input/real_peptides_150.csv", "r") as f:
            reader = csv.DictReader(f)
            peptides = list(reader)
        
        print(f"✓ Loaded {len(peptides)} peptides")
        
        # Check peptide lengths
        lengths = set(len(p['peptide']) for p in peptides)
        print(f"✓ Peptide lengths: {sorted(lengths)}")
        
        # Check HLA alleles
        alleles = set(p['hla_allele'] for p in peptides)
        print(f"✓ HLA alleles: {sorted(alleles)}")
        
        # Check immunogenic distribution
        immunogenic = sum(1 for p in peptides if int(p['immunogenic']) == 1)
        print(f"✓ Immunogenic: {immunogenic}, Non-immunogenic: {len(peptides) - immunogenic}")
        
        return len(peptides) >= 100
        
    except Exception as e:
        print(f"✗ Dataset validation FAILED: {e}")
        return False


def main():
    print("\n" + "=" * 60)
    print("PREDICTOR VALIDATION SUITE")
    print("=" * 60 + "\n")
    
    results = {
        "MHCflurry": test_mhcflurry(),
        "Dataset": test_dataset(),
    }
    
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {test:20s}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✓ ALL VALIDATIONS PASSED - Ready for full run\n")
        return 0
    else:
        print("\n✗ SOME VALIDATIONS FAILED - Fix before proceeding\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
