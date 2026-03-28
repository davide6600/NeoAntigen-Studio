#!/usr/bin/env bash
set -euo pipefail

TESLA_CSV="${1:-}"
if [[ -z "$TESLA_CSV" ]]; then
  echo "Usage: $0 <tesla_supplementary_table2.csv>"
  echo ""
  echo "Download the TESLA dataset from:"
  echo "  https://www.nature.com/articles/s41587-020-0556-3"
  echo "  Supplementary Table 2 (HLA-I validated neoepitopes)"
  echo ""
  echo "The CSV should have columns:"
  echo "  patient_id,peptide,hla_allele,immunogenic"
  exit 1
fi

echo "[1/3] Verifica MHCflurry installato..."
python -c "import sys; print(f'Python version: {sys.version.split()[0]}')" 
if python - <<'PY'
import sys
raise SystemExit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)
PY
then
  python -c "from mhcflurry import Class1PresentationPredictor; Class1PresentationPredictor.load(); print('MHCflurry OK')" \
    || { echo "ERROR: run 'pip install mhcflurry && mhcflurry-downloads fetch' first"; exit 1; }
  PREDICTOR="mhcflurry"
else
  echo "MHCflurry requires Python 3.10-3.12. Falling back to IEDB REST API on this interpreter."
  PREDICTOR="iedb"
fi

echo "[2/3] Esecuzione benchmark con dati reali TESLA..."
python -m benchmark.run_tesla_benchmark \
  --tesla-data "$TESLA_CSV" \
  --predictor "$PREDICTOR" \
  --mode real \
  --output "benchmark/results/real_$(date +%Y%m%d_%H%M%S).json"

echo "[3/3] Report generato in benchmark/results/"
echo ""
echo "NOTA: Questi numeri usano il predictor: $PREDICTOR"
echo "Possono essere citati in un paper dopo validazione."
