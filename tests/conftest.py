# tests/conftest.py
#
# ── Make src/ and scripts/ importable ───────────────────────────────────────
# Files inside src/ and scripts/ import each other directly by module name
# (e.g. "from feature_transformation import ...", not "from src.feature_
# transformation import ..."). Neither directory has an __init__.py, so
# they aren't real Python packages. Tests need the same sys.path setup
# api.py gives itself at runtime, or "import api" / "import promote_model"
# would fail here.

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _dir in ("src", "scripts"):
    sys.path.insert(0, str(PROJECT_ROOT / _dir))   # so tests import modules the same way the app/scripts do
