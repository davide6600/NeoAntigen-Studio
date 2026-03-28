#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW_DIR="${ROOT_DIR}/workflows"
RESULTS_DIR="${1:-${WORKFLOW_DIR}/test-results}"
PIPELINE="${WORKFLOW_DIR}/neoantigen.nf"

if ! command -v nextflow >/dev/null 2>&1; then
  echo "[FAIL] nextflow not found in PATH"
  exit 127
fi

rm -rf "${RESULTS_DIR}"

echo "[INFO] Running NeoAntigen-Studio Nextflow wrapper with profile=test"
nextflow run "${PIPELINE}" -profile test --outdir "${RESULTS_DIR}"

EXPECTED_FILES=(
  "${RESULTS_DIR}/nf_test_sample_hla.txt"
  "${RESULTS_DIR}/nf_test_sample_ranked.json"
  "${RESULTS_DIR}/nf_test_sample_feature_table.json"
  "${RESULTS_DIR}/nf_test_sample_summary.json"
  "${RESULTS_DIR}/nf_test_sample_report.pdf"
)

STATUS=0
for path in "${EXPECTED_FILES[@]}"; do
  if [[ -f "${path}" ]]; then
    echo "[PASS] ${path}"
  else
    echo "[FAIL] missing ${path}"
    STATUS=1
  fi
done

if [[ ${STATUS} -eq 0 ]]; then
  echo "[PASS] Nextflow wrapper smoke test passed"
else
  echo "[FAIL] Nextflow wrapper smoke test failed"
fi

exit ${STATUS}
