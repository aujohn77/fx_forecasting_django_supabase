"""
WSGI config for fx project.
"""

import os
import sys
from pathlib import Path

# --- Make submodule apps importable at runtime (Render) ---
BASE_DIR = Path(__file__).resolve().parent.parent
external = BASE_DIR / "external_apps"

# Find the folder that CONTAINS dop_apps/
matches = list(external.rglob("dop_apps"))
if matches:
    sys.path.insert(0, str(matches[0].parent))
else:
    raise RuntimeError(f"dop_apps not found under {external}. Is the submodule pulled on Render?")

from django.core.wsgi import get_wsgi_application  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fx.settings")

application = get_wsgi_application()
