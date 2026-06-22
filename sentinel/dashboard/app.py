"""Streamlit dashboard for exploring incident data."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st

from sentinel.dashboard.data import load_incidents, resolve_api_url
from sentinel.models import UNMAPPED_TECHNIQUE

st.set_page_config(page_title="ai-sentinel-feed", layout="wide")
st.title("ai-sentinel-feed")
st.caption("Unified AI incident feed: volume, vendors, ATLAS techniques, severity")

api_url = resolve_api_url()
if api_url:
    st.sidebar.caption(f"Data source: API ({api_url})")
else:
    st.sidebar.caption("Data source: PostgreSQL")


@st.cache_data(ttl=300)
def cached_incidents():
    return load_incidents()


def _display_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce nulls for Streamlit/Arrow JSON serialization."""
    out = df.copy()
    out.columns = [
        "(empty)" if c is None or (isinstance(c, float) and pd.isna(c)) else str(c)
        for c in out.columns
    ]
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")
        else:
            out[col] = out[col].fillna("").astype(str).replace("NaT", "")
    return out


try:
    incidents = cached_incidents()
except Exception as exc:
    if api_url:
        st.error(f"Could not load incidents from API ({api_url}): {exc}")
    else:
        st.error(f"Could not load incidents from PostgreSQL: {exc}")
        st.info("For Streamlit Cloud, set secret `SENTINEL_API_URL` to your App Runner URL.")
    st.stop()

if not incidents:
    st.warning("No incidents in the database yet. Run ingest first.")
    st.code("python -m sentinel.pipeline.ingest --source all")
    st.stop()

frame = pd.DataFrame(
    [
        {
            "id": record.id,
            "source": record.source.value,
            "title": record.title,
            "vendor": record.vendor,
            "system": record.system,
            "severity": record.severity.value,
            "atlas_technique": record.atlas_technique,
            "atlas_tactic": record.atlas_tactic,
            "incident_date": record.incident_date,
            "ingested_at": record.ingested_at,
            "url": record.url,
        }
        for record in incidents
    ]
)

with st.sidebar:
    st.header("Filters")
    sources = sorted(frame["source"].dropna().unique())
    severities = sorted(frame["severity"].dropna().unique())
    selected_sources = st.multiselect("Source", sources, default=sources)
    selected_severities = st.multiselect("Severity", severities, default=severities)
    vendor_query = st.text_input("Vendor contains")
    search_query = st.text_input("Search title/description")

filtered = frame[
    frame["source"].isin(selected_sources) & frame["severity"].isin(selected_severities)
]
if vendor_query:
    filtered = filtered[filtered["vendor"].fillna("").str.contains(vendor_query, case=False)]
if search_query:
    mask = filtered["title"].str.contains(search_query, case=False, na=False)
    filtered = filtered[mask]

st.subheader("Incident volume over time")
volume = (
    filtered.assign(period=pd.to_datetime(filtered["incident_date"], errors="coerce").dt.to_period("M").astype(str))
    .groupby(["period", "source"], dropna=False)
    .size()
    .reset_index(name="count")
)
if not volume.empty:
    pivot = volume.pivot(index="period", columns="source", values="count").fillna(0)
    st.line_chart(pivot)
else:
    st.info("No dated incidents for the selected filters.")

left, right = st.columns(2)

with left:
    st.subheader("Severity distribution")
    severity_counts = filtered["severity"].value_counts()
    st.bar_chart(severity_counts)

with right:
    st.subheader("ATLAS technique frequency")
    technique_counts = (
        filtered.loc[filtered["atlas_technique"] != UNMAPPED_TECHNIQUE, "atlas_technique"]
        .value_counts()
        .head(15)
    )
    if technique_counts.empty:
        st.info("No mapped ATLAS techniques yet.")
    else:
        st.bar_chart(technique_counts)

st.subheader("Vendor heatmap")
vendor_tactic = (
    filtered.dropna(subset=["vendor"])
    .groupby(["vendor", "atlas_tactic"], dropna=False)
    .size()
    .reset_index(name="count")
)
if vendor_tactic.empty:
    st.info("No vendor/tactic combinations for the selected filters.")
else:
    vendor_tactic["atlas_tactic"] = vendor_tactic["atlas_tactic"].fillna("(no tactic)")
    heatmap = vendor_tactic.pivot(index="vendor", columns="atlas_tactic", values="count").fillna(0)
    top_vendors = heatmap.sum(axis=1).nlargest(20).index
    st.dataframe(_display_dataframe(heatmap.loc[top_vendors]), use_container_width=True)

st.subheader("Searchable incident table")
table_columns = [
    "source",
    "title",
    "vendor",
    "system",
    "severity",
    "atlas_technique",
    "atlas_tactic",
    "incident_date",
    "ingested_at",
    "url",
]
st.dataframe(
    _display_dataframe(
        filtered.sort_values("ingested_at", ascending=False)[table_columns]
    ),
    use_container_width=True,
    hide_index=True,
)
