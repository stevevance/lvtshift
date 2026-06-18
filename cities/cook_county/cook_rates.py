"""Shared loader for the Cook County Clerk tax-code agency rate file.

Public, freely downloadable from the Clerk's "Tax Extension and Rates" page. The site
blocks the default urllib user-agent (403), so we fetch with requests + a browser UA.
Override the source with the LVT_COOK_RATE_XLSX env var (a URL or local path).
"""
import io
import os

import pandas as pd
import requests

RATE_URL = ("https://www.cookcountyclerkil.gov/sites/default/files/2026-04/"
            "2024-tax-code-agency-rate-file.xlsx")


def read_rate_xlsx(src=None):
    """Return the full agency-rate DataFrame (one row per tax code × agency)."""
    src = src or os.environ.get("LVT_COOK_RATE_XLSX", RATE_URL)
    if str(src).startswith("http"):
        r = requests.get(src, headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
        r.raise_for_status()
        return pd.read_excel(io.BytesIO(r.content))
    return pd.read_excel(src)
