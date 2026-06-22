"""Streamlit dashboard for exploring incident data."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from sentinel.models import UNMAPPED_TECHNIQUE
from sentinel.pipeline import read

st.set_page_config(page_title="ai-sentinel-feed", layout="wide")
st.title("ai-sentinel-feed")
st.caption("Unified AI incident feed — volume, vendors, ATLAS techniques, severity")


@st.cache_data(ttl=300)
def load_incidents():
    return read.list_all_incidents()


try:
    incidents = load_incidents()
except Exception as exc:
    st.error(f"Could not load incidents from PostgreSQL: {exc}")
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
    heatmap = vendor_tactic.pivot(index="vendor", columns="atlas_tactic", values="count").fillna(0)
    st.dataframe(heatmap.style.background_gradient(cmap="Blues", axis=None))

st.subheader("Searchable incident table")
st.dataframe(
    filtered.sort_values("ingested_at", ascending=False),
    use_container_width=True,
    hide_index=True,
)
