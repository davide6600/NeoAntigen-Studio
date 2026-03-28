# Research Use Only (RUO) Policy

## Purpose
This document establishes the binding policy for all utilization of the NeoAntigen-Studio software. NeoAntigen-Studio is designed to identify, evaluate, and design neoantigen sequences and corresponding mRNA constructs for experimental investigation only.

## Binding Assertions
By deploying or using this software, users explicitly agree to the following constraints:

1.  **For Research Use Only:** The software, its algorithms, trained models, and output sequences (peptides, mRNA, DNA) are **NOT INTENDED FOR DIAGNOSTIC OR THERAPEUTIC USE**.
2.  **No Clinical Application:** Predictions or rankings outputted by ML models within this system must not be used to make clinical decisions or direct individual patient care. 
3.  **Experimental Validation Required:** All output sequences (including high-affinity predicted neoantigens and computationally optimized mRNA sequences) are purely in silico hypotheses and must undergo rigorous *in vitro* and *in vivo* testing before any further application.

## System Enforcements
To ensure these guidelines are visible, the software technically enforces the following:
*   **UI Banner:** A prominent, non-dismissible banner displaying the RUO status spans the top of every frontend view in `AppLayout.tsx`.
*   **Export Annotations:** All mRNA/DNA sequence `.fasta` files and their accompanying `.manifest.json` sidecars automatically include a mandatory `"design_intent": "research_use_only"` metadata flag before they can be exported.
*   **Audit Logging:** All human approvals for off-system export explicitly reaffirm this policy prior to authorization.
