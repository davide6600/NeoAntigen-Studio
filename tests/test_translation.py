from __future__ import annotations

from services.worker.phase2_predictors import _translate_codon_to_aa, _translate_to_peptide


def test_translate_codon_to_aa_standard() -> None:
    assert _translate_codon_to_aa("TTT") == "F"
    assert _translate_codon_to_aa("TTC") == "F"
    assert _translate_codon_to_aa("ATG") == "M"
    assert _translate_codon_to_aa("TAA") == "*"
    assert _translate_codon_to_aa("TAG") == "*"
    assert _translate_codon_to_aa("TGA") == "*"
    assert _translate_codon_to_aa("GGT") == "G"
    assert _translate_codon_to_aa("GGA") == "G"


def test_translate_codon_to_aa_wobble_and_unknown() -> None:
    # Testing some from the prompt's specific list
    assert _translate_codon_to_aa("CTT") == "L"
    assert _translate_codon_to_aa("CTC") == "L"
    assert _translate_codon_to_aa("CTA") == "L"
    assert _translate_codon_to_aa("CTG") == "L"
    
    assert _translate_codon_to_aa("GTT") == "V"
    
    assert _translate_codon_to_aa("TCN") == "X" # Non-ACGT
    assert _translate_codon_to_aa("AT") == "X"  # Too short


def test_translate_to_peptide_logic() -> None:
    # 27 nucleotides -> 9 amino acids
    # "ATG" (M), "GTT" (V), "TTT" (F), "TTA" (L), "GGT" (G), "GCT" (A), "TCT" (S), "CCT" (P), "ACT" (T)
    dna = "ATGGTTTTTTTAGGTGCTTCTCCTACT"
    peptide = _translate_to_peptide(dna)
    assert peptide == "MVFLGASPT"
    assert len(peptide) == 9

def test_translate_to_peptide_stops_at_stop_codon() -> None:
    # ATG (M), GTT (V), TAA (Stop), GGT (G)
    dna = "ATGGTTTAAGGT"
    peptide = _translate_to_peptide(dna)
    assert peptide == "MV"

def test_translate_to_peptide_caps_at_9() -> None:
    # 30 nucleotides -> 10 amino acids, should return 9
    dna = "ATG" * 15
    peptide = _translate_to_peptide(dna)
    assert len(peptide) == 9
    assert peptide == "M" * 9
