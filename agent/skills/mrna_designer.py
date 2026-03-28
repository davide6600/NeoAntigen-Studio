from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from agent.auth.rbac import verify_approval
from agent.learnings.store import LearningStore
from agent.skills.sequence_safety import run_safety_scan


SKILL_METADATA = {
    "name": "mrna_designer",
    "capabilities": ["sequence_design_stub", "forbidden_motif_screen", "safe_export_gate"],
    "input_types": ["PEPTIDE", "DESIGN_POLICY"],
    "priority": 70,
    "safety_level": "critical",
}

# Safety rule displayed in the UI and enforced in safe_export:
SAFETY_RULE = (
    "All sequence exports intended for synthesis must pass automatic safety checks "
    "and include an explicit human approval token. "
    "This platform is Research Use Only."
)


def design_sequence(peptides: list[str], linker: str = "GPGPG", species: str = "h_sapiens") -> dict:
    import dnachisel as dc
    import RNA

    if not peptides:
        raise ValueError("At least one peptide is required")
        
    protein = linker.join(peptides)
    initial_dna = dc.reverse_translate(protein)
    
    # Evaluate and adjust sequence to prevent problematic secondary structures
    best_seq = initial_dna
    best_mfe = -9999.0
    best_struct = ""
    
    # We will try up to 3 times to find a sequence with MFE >= -30.0 kcal/mol
    import random
    for attempt in range(3):
        # Add some randomness if not the first attempt by forcing an avoid pattern of a random codon sometimes,
        # but the easiest way to get variety in DnaChisel is to just re-initialize the problem.
        problem = dc.DnaOptimizationProblem(
            sequence=initial_dna,
            constraints=[dc.EnforceTranslation()],
            objectives=[dc.CodonOptimize(species=species)]
        )
        problem.resolve_constraints()
        problem.optimize()
        
        opt_dna = problem.sequence
        rna_seq = opt_dna.replace("T", "U")
        struct, mfe = RNA.fold(rna_seq)
        
        if mfe > best_mfe:
            best_mfe = mfe
            best_seq = opt_dna
            best_struct = struct
            
        if mfe >= -30.0:
            break
            
    is_safe, findings = sequence_safety_check(best_seq)

    return {
        "protein_sequence": protein,
        "dna_sequence": best_seq,
        "rna_sequence": best_seq.replace("T", "U"),
        "vienna_mfe": best_mfe,
        "vienna_structure": best_struct,
        "is_safe": is_safe,
        "safety_findings": findings
    }


def sequence_safety_check(sequence: str) -> tuple[bool, list[str]]:
    """Delegate to the sequence_safety skill for a full blacklist and homopolymer scan."""
    result = run_safety_scan(sequence, dry_run=True)
    return result.is_safe, result.findings


def write_proposal(
    proposal_id: str,
    task: str,
    inputs: list[str],
    outputs: list[str],
    risks: list[str],
    required_approvals: list[str],
) -> Path:
    target = Path("agent/proposals") / f"{proposal_id}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    text = (
        f"# Proposal {proposal_id}\n\n"
        f"- Task: {task}\n"
        f"- Inputs: {', '.join(inputs)}\n"
        f"- Outputs: {', '.join(outputs)}\n"
        f"- Risks: {', '.join(risks)}\n"
        f"- Required approvals: {', '.join(required_approvals)}\n\n"
        f"Approval token format:\n\n`APPROVE: {proposal_id}`\n"
    )
    target.write_text(text, encoding="utf-8")
    return target


def safe_export(
    sequence: str,
    destination_path: str,
    proposal_id: str,
    approval_token: str,
    approved_by: str,
    store: LearningStore | None = None,
    secret_key: str | None = None,
) -> dict:
    """
    Export a sequence to disk with mandatory safety checks and human approval.

    Steps
    -----
    1. Run sequence safety scan (blacklist + homopolymer checks).
    2. Verify the approval token (simple or HMAC-signed) via RBAC.
    3. Write the sequence file and log an audit event.

    Any failure raises ``PermissionError`` and logs a blocked audit event.
    """
    store = store or LearningStore()

    # Step 1 — safety scan
    is_safe, findings = sequence_safety_check(sequence)
    if not is_safe:
        store.append_audit_event(
            action="safe_export",
            status="blocked",
            details={"proposal_id": proposal_id, "reason": "safety_check_failed", "findings": findings},
        )
        raise PermissionError(f"Sequence safety check failed: {findings}")

    # Step 2 — RBAC approval verification
    try:
        identity = verify_approval(
            token=approval_token.strip(),
            proposal_id=proposal_id,
            required_action="safe_export",
            secret_key=secret_key,
        )
    except PermissionError as exc:
        store.append_audit_event(
            action="safe_export",
            status="blocked",
            details={"proposal_id": proposal_id, "reason": str(exc)},
        )
        raise

    # Step 3 — write sequence file and manifest
    import json
    destination = Path(destination_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    
    fasta_content = f">{proposal_id}\n{sequence}\n"
    destination.write_text(fasta_content, encoding="utf-8")
    
    manifest_path = destination.with_suffix(".manifest.json")
    manifest = {
        "proposal_id": proposal_id,
        "approved_by": approved_by,
        "approver_role": identity.role,
        "synthesis_ready_sequence": sequence,
        "timestamp": datetime.now(UTC).isoformat(),
        "manufacturing_notes": "Safety scan passed. Cleared for synthesis. RUO only."
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    event = {
        "proposal_id": proposal_id,
        "approved_by": approved_by,
        "approver_role": identity.role,
        "destination": str(destination),
        "manifest": str(manifest_path),
        "timestamp": datetime.now(UTC).isoformat(),
    }
    store.append_audit_event(action="safe_export", status="approved", details=event)
    return event
