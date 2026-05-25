"""Pytest configuration for dashboard backend tests."""
import sys
from pathlib import Path

# Ensure dashboard package is on the Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))