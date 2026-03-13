"""
Build Editor
------------
Create and edit builds with unified offensive and defensive stats.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
from build_store import (
    OFFENSIVE_FIELDS, DEFENSIVE_FIELDS,
    PCT_FIELDS, INT_FIELDS, SELECT_FIELDS, FLOAT_PCT_FIELDS,
    EDITOR_GROUPS,
    init_store, get_builds, save_build, delete_build,
    get_build_offensive, get_build_defensive,
    render_sidebar,
)

st.set_page_config(page_title="Build Editor", layout="wide")

render_sidebar()

st.title("Build Editor")
st.caption("Create or edit a build by entering its offensive and defensive stats.")

init_store()
builds = get_builds()

# ---------------------------------------------------------------------------
# Build selector
# ---------------------------------------------------------------------------
build_names = list(builds.keys())

# Handle navigation from sidebar edit button — must run before selectbox renders
if "bs_editing" in st.session_state:
    editing_name = st.session_state.pop("bs_editing")
    options_peek = ["— New Build —"] + build_names
    if editing_name in options_peek:
        st.session_state["be_selected"] = editing_name
    st.session_state.pop("_be_prev_sel", None)  # force stat reload

col_sel, col_new = st.columns([3, 1])
with col_sel:
    options = ["— New Build —"] + build_names
    selected = st.selectbox("Select build to edit", options, key="be_selected")
with col_new:
    st.markdown("&nbsp;", unsafe_allow_html=True)

is_new = selected == "— New Build —"

# ---------------------------------------------------------------------------
# Load current values into editor keys when selection changes
# ---------------------------------------------------------------------------
_prev_sel = st.session_state.get("_be_prev_sel")
if _prev_sel != selected:
    st.session_state["_be_prev_sel"] = selected
    st.session_state["be_name"] = "" if is_new else selected
    def _coerce(f, val):
        if f in SELECT_FIELDS:
            return int(val)
        if f in FLOAT_PCT_FIELDS:
            return float(val)
        if f in INT_FIELDS or f in PCT_FIELDS:
            return int(val)
        return float(val)

    if is_new:
        for f, (_, default) in OFFENSIVE_FIELDS.items():
            st.session_state[f"be_off_{f}"] = _coerce(f, default)
        for f, (_, default) in DEFENSIVE_FIELDS.items():
            st.session_state[f"be_def_{f}"] = _coerce(f, default)
    else:
        off = get_build_offensive(selected)
        defn = get_build_defensive(selected)
        for f, val in off.items():
            st.session_state[f"be_off_{f}"] = _coerce(f, val)
        for f, val in defn.items():
            st.session_state[f"be_def_{f}"] = _coerce(f, val)

# ---------------------------------------------------------------------------
# Build name input
# ---------------------------------------------------------------------------
name_default = "" if is_new else selected
build_name = st.text_input("Build name", value=name_default, key="be_name",
                            placeholder="Enter a name for this build")

st.divider()


# ---------------------------------------------------------------------------
# Input renderer
# ---------------------------------------------------------------------------
#TODO: Move the Weapon Size Modifier % and Elemental Counter % from the Build Editor
#      to the DMG Calculator and Stat Optimizer pages. These stats are not universal,
#      but change depending on the damage calculation and aren't tied to the character.
#      Moving to the damage calculation pages is better aligned with game behavior
def _render_input(field: str, label: str, default, key: str):
    if field in SELECT_FIELDS:
        options = SELECT_FIELDS[field]
        cur = st.session_state.get(key, int(default))
        idx = options.index(cur) if cur in options else 0
        return st.selectbox(label, options=options, index=idx,
                            format_func=lambda x: f"{x}%", key=key)
    elif field in FLOAT_PCT_FIELDS:
        return st.number_input(label, value=float(st.session_state.get(key, default)),
                               min_value=0.0, step=0.01, format="%.2f", key=key)
    elif field in PCT_FIELDS or field in INT_FIELDS:
        return st.number_input(label, value=int(st.session_state.get(key, default)),
                               min_value=0, step=1, key=key)
    else:
        return st.number_input(label, value=float(st.session_state.get(key, default)),
                               min_value=0.0, key=key)


# ---------------------------------------------------------------------------
# Grouped stat inputs (offensive left, defensive right)
# ---------------------------------------------------------------------------
off_vals = {}
def_vals = {}

for grp_label, icon, off_keys, def_keys, _, _ in EDITOR_GROUPS:
    if not off_keys and not def_keys:
        continue
    with st.expander(f"{icon} **{grp_label}**", expanded=False):
        col_off, col_def = st.columns(2)
        with col_off:
            if off_keys:
                st.markdown("**Offensive**")
            for f in off_keys:
                label, default = OFFENSIVE_FIELDS[f]
                off_vals[f] = _render_input(f, label, default, f"be_off_{f}")
        with col_def:
            if def_keys:
                st.markdown("**Defensive**")
            for f in def_keys:
                label, default = DEFENSIVE_FIELDS[f]
                def_vals[f] = _render_input(f, label, default, f"be_def_{f}")

# Fill in any fields not covered by groups
for f, (label, default) in OFFENSIVE_FIELDS.items():
    if f not in off_vals:
        off_vals[f] = st.session_state.get(f"be_off_{f}", default)
for f, (label, default) in DEFENSIVE_FIELDS.items():
    if f not in def_vals:
        def_vals[f] = st.session_state.get(f"be_def_{f}", default)

st.divider()

# ---------------------------------------------------------------------------
# Save / Delete buttons
# ---------------------------------------------------------------------------
col_save, col_del, _ = st.columns([1, 1, 6])
with col_save:
    if st.button("💾 Save Build", type="primary", use_container_width=True):
        name = build_name.strip()
        if not name:
            st.error("Enter a build name.")
        else:
            save_build(name, off_vals, def_vals)
            st.session_state["_bs_file_loaded"] = True
            if is_new:
                # Force stat reset to defaults on rerun so the form is clean
                st.session_state.pop("_be_prev_sel", None)
            st.toast(f"Saved '{name}'", icon="✅")
            st.rerun()

with col_del:
    if not is_new:
        if st.button("🗑️ Delete Build", use_container_width=True):
            delete_build(selected)
            st.session_state.pop("_be_prev_sel", None)
            st.toast(f"Deleted '{selected}'", icon="✅")
            st.rerun()