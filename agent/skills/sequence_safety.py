from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SKILL_METADATA = {
    "name": "sequence_safety",
    "capabilities": ["homology_check", "blacklist_screen", "dry_run_safety_scan"],
    "input_types": ["PEPTIDE", "SEQUENCE"],
    "priority": 95,
    "safety_level": "critical",
}

_DEFAULT_BLACKLIST_MOTIFS = [
    ("TOXIN", "local_default", "hazard_marker"),
    ("PATHOGEN", "local_default", "hazard_marker"),
    ("VENOM", "local_default", "hazard_marker"),
    ("AAAAAAAATTTTTTT", "local_default", "homopolymer"),
    ("RICIN", "local_default", "protein_toxin"),
    ("BOTULINUM", "local_default", "protein_toxin"),
]


@dataclass
class BlacklistEntry:
    motif: str
    source: str
    hazard_class: str
    notes: str = ""


@dataclass
class SafetyScanResult:
    is_safe: bool
    findings: list[str]
    dry_run: bool


def load_blacklist(path: str | Path | None = None) -> list[BlacklistEntry]:
    """Load blacklist entries from a tab-delimited file, falling back to built-in defaults."""
    target = Path(path) if path else Path("data/sequence_blacklist.txt")
    entries: list[BlacklistEntry] = []

    if target.exists():
        for line in target.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            entries.append(
                BlacklistEntry(
                    motif=parts[0],
                    source=parts[1] if len(parts) > 1 else "local_blacklist",
                    hazard_class=parts[2] if len(parts) > 2 else "unclassified",
                )
            )
    else:
        for motif, source, hazard_class in _DEFAULT_BLACKLIST_MOTIFS:
            entries.append(BlacklistEntry(motif=motif, source=source, hazard_class=hazard_class))

    return entries


def homology_check(sequence: str, blacklist: list[BlacklistEntry]) -> list[str]:
    """Check sequence against the blacklist and flag homopolymer runs."""
    findings: list[str] = []
    seq_upper = sequence.upper()

    for entry in blacklist:
        if entry.motif.upper() in seq_upper:
            findings.append(
                f"Blacklist match: motif='{entry.motif}' source='{entry.source}' "
                f"hazard='{entry.hazard_class}'"
            )

    homopolymer_threshold = 9
    for base in "ACGTU":
        if base * homopolymer_threshold in seq_upper:
            findings.append(
                f"Homopolymer run >={homopolymer_threshold} for base '{base}'"
            )

    return findings


def run_safety_scan(
    sequence: str,
    dry_run: bool = True,
    blacklist_path: str | Path | None = None,
) -> SafetyScanResult:
    """
    Run a full safety scan on a sequence.

    In dry-run mode the result is informational and no side effects occur.
    In non-dry-run mode findings are logged and can block export.
    """
    blacklist = load_blacklist(blacklist_path)
    findings = homology_check(sequence, blacklist)
    return SafetyScanResult(is_safe=len(findings) == 0, findings=findings, dry_run=dry_run)
