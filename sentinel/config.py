"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
EXPORTS_DIR = DATA_DIR / "exports"
ATLAS_DIR = DATA_DIR / "atlas"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://sentinel:sentinel@localhost:5432/sentinel",
)
AIAAIC_CSV_URL = os.getenv(
    "AIAAIC_CSV_URL",
    "https://docs.google.com/spreadsheets/d/1Bn55B4xz21-_Rgdr8BBb2lt0n_4rzLGxFADMlVW0PYI/export?format=csv&gid=888071280",
)
NVD_API_KEY = os.getenv("NVD_API_KEY", "")
NVD_API_URL = os.getenv(
    "NVD_API_URL",
    "https://services.nvd.nist.gov/rest/json/cves/2.0",
)
NVD_KEYWORDS = [
    keyword.strip()
    for keyword in os.getenv(
        "NVD_KEYWORDS",
        "pytorch,tensorflow,langchain,huggingface",
    ).split(",")
    if keyword.strip()
]
AIID_GRAPHQL_URL = os.getenv(
    "AIID_GRAPHQL_URL",
    "https://incidentdatabase.ai/api/graphql",
)
