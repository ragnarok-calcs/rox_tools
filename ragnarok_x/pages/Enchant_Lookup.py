


"""
Enchant Lookup
--------------
Look up enchant stat values and quality probabilities from enchants_db.json.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from pathlib import Path
from build_store import render_sidebar
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Enchant Lookup", layout="wide")
render_sidebar()
st.title("Enchant Lookup")

# ---------------------------------------------------------------------------
# Load DB
# ---------------------------------------------------------------------------
_DB_PATH = Path(__file__).parent.parent / "data" / "enchants_db.json"

@st.cache_data
def _load_db() -> pd.DataFrame:
    with open(_DB_PATH, encoding="utf-8") as f:
        data = json.load(f)
    result = pd.DataFrame(data)
    # Ensure numeric columns
    for col in ("level", "white", "blue", "purple", "orange",
                "prob_white", "prob_blue", "prob_purple", "prob_orange"):
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")
    return result

df = _load_db()

# ---------------------------------------------------------------------------
# Filter controls
# ---------------------------------------------------------------------------
col_level, col_city, col_equip, col_stat = st.columns([1, 2, 2, 3])

with col_level:
    level = st.number_input(
        "Enchant Level", min_value=1, max_value=20, value=10, step=1,
        help="The enchant level (1–20)"
    )

with col_city:
    all_cities = sorted(df["location"].dropna().unique().tolist())
    selected_cities = st.multiselect(
        "City", options=all_cities,
        placeholder="All cities"
    )

with col_equip:
    all_equip = sorted(df["equipment_en"].dropna().unique().tolist())
    selected_equip = st.multiselect(
        "Equipment", options=all_equip,
        placeholder="All equipment"
    )

with col_stat:
    all_stats = sorted(df["stat_en"].dropna().unique().tolist())
    selected_stats = st.multiselect(
        "Stat", options=all_stats,
        placeholder="All stats"
    )

# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------
mask = df["level"] == level

if selected_cities:
    mask &= df["location"].isin(selected_cities)
if selected_equip:
    mask &= df["equipment_en"].isin(selected_equip)
if selected_stats:
    mask &= df["stat_en"].isin(selected_stats)

filtered = df[mask].copy()

st.caption(f"{len(filtered)} result{'s' if len(filtered) != 1 else ''} at enchant level {level}")

if filtered.empty:
    st.info("No enchants match the current filters.")
    st.stop()

# ---------------------------------------------------------------------------
# Build display table
# ---------------------------------------------------------------------------
has_probs = "prob_white" in filtered.columns and filtered["prob_white"].notna().any()

display_cols = {
    "location":     "City",
    "equipment_en": "Equipment",
    "stat_en":      "Stat",
    "white":        "White",
    "blue":         "Blue",
    "purple":       "Purple",
    "orange":       "Orange",
}

if has_probs:
    display_cols.update({
        "prob_white":  "P(White) %",
        "prob_blue":   "P(Blue) %",
        "prob_purple": "P(Purple) %",
        "prob_orange": "P(Orange) %",
    })

out = (
    filtered[list(display_cols.keys())]
    .rename(columns=display_cols)
    .sort_values(["City", "Equipment", "Stat"])
    .reset_index(drop=True)
)

# Format value and probability columns to 2 decimal places
prob_cols = [c for c in out.columns if c.startswith("P(")]
value_cols = ["White", "Blue", "Purple", "Orange"]
fmt = {c: "{:.2f}" for c in prob_cols + value_cols if c in out.columns}

st.dataframe(
    out.style.format(fmt, na_rep="—"),
    use_container_width=True,
    hide_index=True,
)