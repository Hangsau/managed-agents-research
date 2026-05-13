"""Conftest for Hermes core tests."""
import sys
from pathlib import Path

# Make heartbeat_v2.py importable from ~/.hermes/scripts/
sys.path.insert(0, str(Path("~/.hermes/scripts").expanduser()))
