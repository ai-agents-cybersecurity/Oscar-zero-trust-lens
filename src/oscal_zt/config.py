# src/oscal_zt/config.py
"""
Configuration for OSCAL Zero Trust Lens.
"""
from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]

# Load environment variables from repo-level .env if present
load_dotenv(BASE_DIR / ".env")

OSCAL_CONTENT_DIR = BASE_DIR / "data" / "oscal-content"

# Example 800-53 catalog
OSCAL_CATALOG_PATH = (
    OSCAL_CONTENT_DIR
    / "nist.gov"
    / "SP800-53"
    / "rev5"
    / "json"
    / "NIST_SP-800-53_rev5_catalog.json"
)

# Example SSP
DEMO_SSP_PATH = BASE_DIR / "data" / "ssp" / "demo-ssp.json"

# ZT Lens storage
ZT_LENS_DIR = BASE_DIR / "data" / "zt_lens"
ZT_LENS_PATH = ZT_LENS_DIR / "zt-lens-800-53.json"

# LLM config
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
