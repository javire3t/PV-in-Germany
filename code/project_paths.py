"""Shared project paths, independent of the terminal's working directory.

The project root holds code/, data/, results/ (shareable figures and workbooks)
and validation/ (internal audit outputs).
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The user-editable figure settings live in the project root.
_spec = importlib.util.spec_from_file_location("settings", ROOT / "settings.py")
settings = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(settings)
CODE = ROOT / "code"

DATA = ROOT / "data"
RAW = DATA / "raw"
BOUNDARIES = RAW / "boundaries"
ENERGY_CHARTS = RAW / "energy_charts"
NEP_SOURCES = RAW / "nep"
NEP_ESTIMATES = DATA / "processed" / "nep_estimates"
BKG_GEOJSON = BOUNDARIES / "germany_districts_bkg_2025.geojson"
# Animation frames, annual maps and export checks; safe to delete and regenerate.
INTERMEDIATE_OUTPUTS = DATA / "work"

RESULTS = ROOT / "results"
FINAL_OUTPUTS = RESULTS / "figures"
FINAL_EXCEL = RESULTS / "excel"
VALIDATION_RESULTS = ROOT / "validation"
WORKBOOK = FINAL_EXCEL / "energy-charts_solar_capacity.xlsx"
