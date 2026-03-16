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
    get_build_offensive, get_build_defensive, get_build_weapon_meta,
    render_sidebar,
)
from data.enchants_data import (
    get_enchant_awakening_info, get_weapon_enchant_options,
    ENCHANT_STAT_FIELD_MAP, ENCHANT_STAT_LABELS, QUALITY_OPTIONS,
    MAX_ENCHANT_AWAKENING,
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

    # Load weapon meta
    from build_store import _wm_defaults
    wm = _wm_defaults() if is_new else get_build_weapon_meta(selected)
    st.session_state["be_wm_weapon_type"]  = wm["weapon_type"]
    st.session_state["be_wm_awakening"]    = int(wm["enchant_awakening"])
    st.session_state["be_wm_drake_card"]   = bool(wm.get("drake_card", False))
    for i in range(3):
        enc = (wm["main_enchants"] or [None, None, None])
        slot = enc[i] if i < len(enc) else None
        st.session_state[f"be_wm_main_{i}_stat"] = slot["stat_en"] if slot else "None"
        st.session_state[f"be_wm_main_{i}_qual"] = slot["quality"] if slot else "Orange"
        enc = (wm["sub_enchants"] or [None, None, None])
        slot = enc[i] if i < len(enc) else None
        st.session_state[f"be_wm_sub_{i}_stat"] = slot["stat_en"] if slot else "None"
        st.session_state[f"be_wm_sub_{i}_qual"] = slot["quality"] if slot else "Orange"

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

# ---------------------------------------------------------------------------
# Weapon Enchants (metadata for Enchant Optimizer)
# ---------------------------------------------------------------------------
with st.expander("⚗️ **Weapon Enchants**", expanded=False):
    st.caption("Record your current weapon enchants. Used by the Enchant Optimizer to find improvements.")
    col_wt, col_awk = st.columns(2)
    with col_wt:
        weapon_type = st.radio(
            "Weapon Type", ["one-handed", "two-handed"],
            format_func=lambda x: x.title(),
            horizontal=True, key="be_wm_weapon_type",
        )
    with col_awk:
        awakening = st.number_input(
            "Enchant Awakening Level", min_value=0, max_value=MAX_ENCHANT_AWAKENING,
            step=1, key="be_wm_awakening",
        )

    awk_info = get_enchant_awakening_info(awakening)
    st.caption(f"Enchant Level: **{awk_info['enchant_lvl']}**  ·  Modifier: **×{awk_info['modifier']:.1f}**")

    all_stat_names = ["None"] + list(ENCHANT_STAT_FIELD_MAP.keys())

    def _enchant_slot_row(prefix: str, i: int, wtype: str) -> dict | None:
        col_s, col_q = st.columns([3, 2])
        with col_s:
            stat = st.selectbox(
                f"Slot {i + 1}", all_stat_names,
                key=f"{prefix}_{i}_stat", label_visibility="collapsed",
            )
        with col_q:
            qual = st.selectbox(
                "Quality", QUALITY_OPTIONS,
                key=f"{prefix}_{i}_qual", label_visibility="collapsed",
                disabled=(stat == "None"),
            )
        if stat != "None":
            opts = get_weapon_enchant_options(wtype, awk_info["enchant_lvl"], qual, awk_info["modifier"])
            opt_map = {o["stat_en"]: o for o in opts}
            if stat in opt_map:
                eff = opt_map[stat]["effective_value"]
                st.caption(f"+{eff:g}  ({ENCHANT_STAT_LABELS.get(stat, stat)})")
            return {"stat_en": stat, "quality": qual}
        return None

    st.markdown("**Main Weapon**")
    main_enchants = [_enchant_slot_row("be_wm_main", i, weapon_type) for i in range(3)]

    sub_enchants: list[dict | None] = [None, None, None]
    if weapon_type == "one-handed":
        st.markdown("**Sub-Weapon**")
        sub_enchants = [_enchant_slot_row("be_wm_sub", i, "sub") for i in range(3)]

# ---------------------------------------------------------------------------
# Card Effects
# ---------------------------------------------------------------------------
with st.expander("🃏 **Card Effects**", expanded=False):
    drake_card = st.toggle(
        "Drake Card",
        value=st.session_state.get("be_wm_drake_card", False),
        key="be_wm_drake_card",
        help=(
            "Drake Card: removes the size modifier from damage calculations. "
            "The size multiplier is treated as ×1.0 regardless of weapon type or size bonuses."
        ),
    )

weapon_meta = {
    "weapon_type":       st.session_state.get("be_wm_weapon_type", "one-handed"),
    "enchant_awakening": st.session_state.get("be_wm_awakening",   0),
    "main_enchants":     main_enchants,
    "sub_enchants":      sub_enchants,
    "drake_card":        st.session_state.get("be_wm_drake_card",  False),
}

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
            save_build(name, off_vals, def_vals, weapon_meta)
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