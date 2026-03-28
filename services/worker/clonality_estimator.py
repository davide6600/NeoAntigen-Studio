"""
clonality_estimator.py
----------------------
Estimates cancer cell fraction (CCF) per variant to classify neoantigens
as clonal (CCF ≈ 1.0) or subclonal (CCF < clonal_threshold).

Two estimation modes
--------------------
1. pyclone_vi  : Calls PyClone-VI (Gillis & Bhatt, 2021) when available.
                 Requires pyclone-vi installed and in PATH.
2. simple_ccf  : Lightweight analytic CCF estimate from VAF, purity, and
                 local copy number — no external dependencies.

The simple_ccf formula (Landau et al. 2013 / McGranahan & Swanton 2015):
    CCF = VAF * (purity * CN_total + (1 - purity) * 2) / (purity * CN_mut)
    where CN_mut defaults to 1 (heterozygous somatic mutation).

Public API
----------
estimate_clonality(variants_df, mode="simple_ccf", purity=1.0,
                   clonal_threshold=0.8, pyclone_output_dir=None)
    -> pd.DataFrame
    Returns input DataFrame with added columns:
        ccf          : float  (Cancer Cell Fraction, 0–1)
        is_clonal    : bool   (ccf >= clonal_threshold)
        clonality    : str    ("clonal" | "subclonal" | "unknown")
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Literal, Optional
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

import numpy as np

logger = logging.getLogger(__name__)

_PYCLONE_REQUIRED_COLS = ["mutation_id", "ref_counts", "alt_counts",
                           "normal_cn", "minor_cn", "major_cn"]


# ──────────────────────────────────────────────────────────────────────────────
# CCF estimation modes
# ──────────────────────────────────────────────────────────────────────────────

def _simple_ccf(
    vaf: pd.Series,
    purity: float,
    cn_total: pd.Series,
    cn_mut: pd.Series,
) -> pd.Series:
    """
    Analytic CCF from VAF, purity, local total CN and mutant CN.

    CCF = VAF * (purity * cn_total + (1 - purity) * 2) / (purity * cn_mut)

    Clips output to [0, 1] — values > 1 indicate CN gain on the mutant allele
    or purity underestimation; we cap at 1 (effectively clonal).
    """
    numerator   = vaf * (purity * cn_total + (1.0 - purity) * 2.0)
    denominator = purity * cn_mut
    # Avoid division by zero
    safe_denom = denominator.replace(0, np.nan)
    ccf = (numerator / safe_denom).clip(0.0, 1.0)
    return ccf.fillna(0.0)


def _run_pyclone_vi(
    variants_df: pd.DataFrame,
    purity: float,
    output_dir: Optional[str | Path],
) -> pd.DataFrame:
    """
    Write PyClone-VI input, run inference, parse output.
    Raises RuntimeError if pyclone-vi is not installed or fails.
    """
    for col in _PYCLONE_REQUIRED_COLS:
        if col not in variants_df.columns:
            raise ValueError(
                f"PyClone-VI mode requires column '{col}'. "
                f"Available: {list(variants_df.columns)}"
            )

    tmpdir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
    tmpdir.mkdir(parents=True, exist_ok=True)

    input_file  = tmpdir / "pyclone_input.tsv"
    output_file = tmpdir / "pyclone_output.tsv"

    pyclone_input = variants_df[_PYCLONE_REQUIRED_COLS].copy()
    pyclone_input["tumour_content"] = purity
    pyclone_input.to_csv(input_file, sep="\t", index=False)

    cmd = [
        "pyclone-vi", "fit",
        "--in-file",      str(input_file),
        "--out-file",     str(output_file),
        "--num-clusters", "10",
        "--num-restarts", "5",
        "--seed",         "42",
    ]

    logger.info("clonality_estimator: running PyClone-VI: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"PyClone-VI failed (exit {result.returncode}):\n{result.stderr}"
        )

    import pandas as pd
    pyclone_out = pd.read_csv(output_file, sep="\t")
    # PyClone-VI output has columns: mutation_id, sample_id, cellular_prevalence, ...
    ccf_map = (
        pyclone_out.groupby("mutation_id")["cellular_prevalence"]
        .mean()
        .rename("ccf")
    )

    result_df = variants_df.copy()
    result_df = result_df.join(ccf_map, on="mutation_id", how="left")
    result_df["ccf"] = result_df["ccf"].fillna(0.0).clip(0.0, 1.0)
    return result_df


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def estimate_clonality(
    variants_df: pd.DataFrame,
    mode: Literal["simple_ccf", "pyclone_vi"] = "simple_ccf",
    purity: float = 1.0,
    clonal_threshold: float = 0.8,
    cn_total_col: str = "cn_total",
    cn_mut_col: str = "cn_mut",
    vaf_col: str = "vaf",
    pyclone_output_dir: Optional[str | Path] = None,
) -> pd.DataFrame:
    """
    Add CCF-based clonality annotation to a variants DataFrame.

    Parameters
    ----------
    variants_df : pd.DataFrame
        Must contain at minimum:
          - 'vaf'      (float, 0–1)  for simple_ccf mode
          - PyClone-VI columns       for pyclone_vi mode
    mode : str
        'simple_ccf' (default, no dependencies) or 'pyclone_vi'.
    purity : float
        Tumour purity estimate (0–1). Defaults to 1.0 (pure tumour).
    clonal_threshold : float
        CCF >= this value → clonal. Default 0.8.
    cn_total_col : str
        Column with total local copy number. Default 'cn_total'.
        If missing, assumes diploid (cn_total = 2).
    cn_mut_col : str
        Column with mutant allele copy number. Default 'cn_mut'.
        If missing, assumes heterozygous (cn_mut = 1).
    vaf_col : str
        Column with variant allele frequency. Default 'vaf'.
    pyclone_output_dir : str | Path, optional
        Directory for PyClone-VI temp files. Defaults to system tmpdir.

    Returns
    -------
    pd.DataFrame
        Input DataFrame + columns: ['ccf', 'is_clonal', 'clonality']
    """
    if variants_df.empty:
        logger.warning("clonality_estimator: received empty variants_df, returning as-is.")
        df = variants_df.copy()
        import pandas as pd
        df["ccf"] = pd.Series(dtype=float)
        df["is_clonal"] = pd.Series(dtype=bool)
        df["clonality"] = pd.Series(dtype=str)
        return df

    if mode == "pyclone_vi":
        df = _run_pyclone_vi(variants_df, purity, pyclone_output_dir)

    elif mode == "simple_ccf":
        if vaf_col not in variants_df.columns:
            raise ValueError(
                f"simple_ccf mode requires column '{vaf_col}'. "
                f"Available: {list(variants_df.columns)}"
            )
        df = variants_df.copy()

        # Use provided CN columns or fall back to diploid / heterozygous defaults
        import pandas as pd
        cn_total = (
            df[cn_total_col].astype(float)
            if cn_total_col in df.columns
            else pd.Series(2.0, index=df.index)
        )
        cn_mut = (
            df[cn_mut_col].astype(float)
            if cn_mut_col in df.columns
            else pd.Series(1.0, index=df.index)
        )

        df["ccf"] = _simple_ccf(
            vaf=df[vaf_col].astype(float),
            purity=purity,
            cn_total=cn_total,
            cn_mut=cn_mut,
        )
    else:
        raise ValueError(f"Unknown mode '{mode}'. Choose 'simple_ccf' or 'pyclone_vi'.")

    df["is_clonal"]  = df["ccf"] >= clonal_threshold
    df["clonality"]  = df["is_clonal"].map({True: "clonal", False: "subclonal"})

    n_clonal    = df["is_clonal"].sum()
    n_total     = len(df)
    logger.info(
        "clonality_estimator: %d / %d variants classified as clonal (CCF >= %.2f)",
        n_clonal, n_total, clonal_threshold,
    )

    return df