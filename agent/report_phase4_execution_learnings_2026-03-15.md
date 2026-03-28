# Phase 4 Execution Learnings (2026-03-15)

## Objective
Implement Phase 4: mRNA Designer + Safety-Hardened Export, which involves integrating DnaChisel for codon optimization, ViennaRNA for structural evaluations, and building out secure API endpoints for generating export manifest payloads under Biosecurity Officer authorizations.

## What went well
1. **Sidecar Manifest Pattern**: Generating a `.manifest.json` parallel to the raw `.fasta` artifact proved to be a clean way to package manufacturing metadata (like RUO notes and the precise approver role) without polluting the sequence file format.
2. **Decoupled Safety Scanning**: By keeping `sequence_safety_check` completely isolated from `design_sequence` generation loop, we enabled a unified validation path. It executes against both externally supplied sequences and internal dynamically generated ones, standardizing the `is_safe` output.
3. **Audit Immutability**: Appending rejected API attempts instantly to the learning store (e.g. testing invalid IDs or failed RBAC checks) successfully maintained high system observability.

## Pitfalls & Fixes
1. **Pyre Static Typing with UUID**: Directly string-slicing a UUID object (`uuid.uuid4().hex[:8]`) triggers static type analysis errors, as Pyre isn't always certain the indexed target is purely string. **Fix**: Explicitly cast using `str(uuid.uuid4())[:8]` uniformly.
2. **Pydantic V2 Deprecations**: The `min_items` parameter within the `Field` class is actively deprecated and warns loudly during pytest runs. **Fix**: Switched to `min_length` to respect current V2 specifications.
3. **Tool API Quirks**: ViennaRNA requires RNA input (`U` instead of `T`), whilst DnaChisel naturally operates on DNA strings. **Fix**: Enforced a strict boundary of replacing `"T"` with `"U"` only just preceding `RNA.fold()` calls to avoid mixed-type bugs.

## Repository Changes
- Created unified generation behavior using `DnaChisel` and `RNA.fold` in `agent/skills/mrna_designer.py`.
- Exposed computational design capabilities over `POST /mrna/design` within `services/api/main.py`.
- Added RBAC-controlled export orchestration via `POST /mrna/export` outputting dual `.fasta` / `.manifest.json` files.
