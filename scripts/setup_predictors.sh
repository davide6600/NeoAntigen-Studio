#!/usr/bin/env bash
set -euo pipefail
PY_VERSION="$(python -c 'import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")')"
echo "Detected Python ${PY_VERSION}"

if ! python - <<'PY'
import sys
if not ((3, 10) <= sys.version_info[:2] <= (3, 12)):
    raise SystemExit(1)
PY
then
  echo "MHCflurry requires Python 3.10-3.12."
  echo "On Python 3.13+, NeoAntigen-Studio uses the IEDB REST API automatically."
  exit 0
fi

pip install mhcflurry
mhcflurry-downloads fetch
python -c "
from mhcflurry import Class1PresentationPredictor
p = Class1PresentationPredictor.load()
r = p.predict(['GILGFVFTL'], ['HLA-A02:01'])
print('MHCflurry OK, affinity:', r.iloc[0].get('mhcflurry_affinity'))
"
