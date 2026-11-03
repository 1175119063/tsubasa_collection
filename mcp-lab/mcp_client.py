"""Compatibility entry point; implementation lives in app.inat_mcp.mcp_client."""
import os
import sys
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB_DIR.parent / "backend"))
os.environ.setdefault("TSUBASA_INAT_CACHE_DIR", str(LAB_DIR / "cache"))
os.environ.setdefault("TSUBASA_INAT_ALIASES_DIR", str(LAB_DIR))
from app.inat_mcp import mcp_client as implementation  # noqa: E402

sys.modules[__name__] = implementation
