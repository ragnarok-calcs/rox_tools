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
    PCT_FIELDS, INT_FIELDS, FLOAT_PCT_FIELDS, SCENARIO_SELECT_FIELDS,
    EDITOR_GROUPS,
    init_store, get_builds, save_build, delete_build,
    get_build_offensive, get_build_defensive, get_build_weapon_meta,
    render_sidebar,
)
from data.enchants_data import (
    get_enchant_awakening_info, get_weapon_enchant_options,
    get_enchant_cities_for_stat, get_max_awakening_for_enchant_levels,
    ENCHANT_STAT_FIELD_MAP, ENCHANT_STAT_LABELS, QUALITY_OPTIONS,
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
        if f in SCENARIO_SELECT_FIELDS:
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
    st.session_state["be_wm_weapon_type"]          = wm["weapon_type"]
    st.session_state["be_wm_weapon_enchant_lvl"]   = int(wm.get("weapon_enchant_lvl", 0))
    st.session_state["be_wm_armor_enchant_lvl"]    = int(wm.get("armor_enchant_lvl", 0))
    st.session_state["be_wm_accessory_enchant_lvl"] = int(wm.get("accessory_enchant_lvl", 0))
    st.session_state["be_wm_awakening"]            = int(wm["enchant_awakening"])
    st.session_state["be_wm_drake_card"]           = bool(wm.get("drake_card", False))
    for i in range(3):
        enc = (wm["main_enchants"] or [None, None, None])
        slot = enc[i] if i < len(enc) else None
        st.session_state[f"be_wm_main_{i}_stat"] = slot["stat_en"] if slot else "None"
        st.session_state[f"be_wm_main_{i}_qual"] = slot["quality"] if slot else "Orange"
        st.session_state[f"be_wm_main_{i}_city"] = slot.get("city") if slot else None
        _default_lvl = int(wm.get("weapon_enchant_lvl") or 1)
        st.session_state[f"be_wm_main_{i}_lvl"]  = int(slot.get("level", _default_lvl)) if slot else _default_lvl
        enc = (wm["sub_enchants"] or [None, None, None])
        slot = enc[i] if i < len(enc) else None
        st.session_state[f"be_wm_sub_{i}_stat"] = slot["stat_en"] if slot else "None"
        st.session_state[f"be_wm_sub_{i}_qual"] = slot["quality"] if slot else "Orange"
        st.session_state[f"be_wm_sub_{i}_city"] = slot.get("city") if slot else None
        st.session_state[f"be_wm_sub_{i}_lvl"]  = int(slot.get("level", _default_lvl)) if slot else _default_lvl

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
def _render_input(field: str, label: str, default, key: str):
    if field in FLOAT_PCT_FIELDS:
        return st.number_input(label, value=float(st.session_state.get(key, default)),
                               min_value=0.0, step=0.01, format="%.2f", key=key)
    elif field in PCT_FIELDS or field in INT_FIELDS:
        return st.number_input(label, value=int(st.session_state.get(key, default)),
                               min_value=0, step=1, key=key)
    else:
        return st.number_input(label, value=float(st.session_state.get(key, default)),
                               min_value=0.0, key=key)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_stats, tab_enchants, tab_cards = st.tabs(["📊 Damage Stats", "⚗️ Enchants", "🃏 Cards"])

# ── Tab 1: Damage Stats ───────────────────────────────────────────────────
off_vals = {}
def_vals = {}

with tab_stats:
    for grp_label, icon, off_keys, def_keys, _, _ in EDITOR_GROUPS:
        if not off_keys and not def_keys:
            continue
        with st.expander(f"{icon} **{grp_label}**", expanded=False):
            col_off, col_def = st.columns(2)
            with col_off:
                if off_keys:
                    st.markdown("**Offensive**")
                for f in off_keys:
                    if f in SCENARIO_SELECT_FIELDS:
                        continue
                    label, default = OFFENSIVE_FIELDS[f]
                    off_vals[f] = _render_input(f, label, default, f"be_off_{f}")
            with col_def:
                if def_keys:
                    st.markdown("**Defensive**")
                for f in def_keys:
                    label, default = DEFENSIVE_FIELDS[f]
                    def_vals[f] = _render_input(f, label, default, f"be_def_{f}")

# Fill in any fields not covered by groups (runs outside tab so always populated)
for f, (label, default) in OFFENSIVE_FIELDS.items():
    if f not in off_vals:
        off_vals[f] = st.session_state.get(f"be_off_{f}", default)
for f, (label, default) in DEFENSIVE_FIELDS.items():
    if f not in def_vals:
        def_vals[f] = st.session_state.get(f"be_def_{f}", default)

# ── Tab 2: Enchants ───────────────────────────────────────────────────────
with tab_enchants:
    st.caption("Record your current enchant levels and active enchants. Used by the Enchant Optimizer.")

    # Enchant levels & awakening
    st.markdown("**Enchant Levels**")
    col_wlvl, col_alvl, col_aclvl = st.columns(3)
    with col_wlvl:
        weapon_enchant_lvl = st.number_input(
            "Weapon", min_value=0, max_value=20, step=1,
            key="be_wm_weapon_enchant_lvl",
            help="Your weapon's current enchant level (0–20).",
        )
    with col_alvl:
        armor_enchant_lvl = st.number_input(
            "Armor", min_value=0, max_value=20, step=1,
            key="be_wm_armor_enchant_lvl",
            help="Your armor's current enchant level (0–20).",
        )
    with col_aclvl:
        accessory_enchant_lvl = st.number_input(
            "Accessory", min_value=0, max_value=20, step=1,
            key="be_wm_accessory_enchant_lvl",
            help="Your accessory's current enchant level (0–20).",
        )

    max_awakening = get_max_awakening_for_enchant_levels(
        weapon_enchant_lvl, armor_enchant_lvl, accessory_enchant_lvl
    )
    if st.session_state.get("be_wm_awakening", 0) > max_awakening:
        st.session_state["be_wm_awakening"] = max_awakening

    col_wt, col_awk = st.columns(2)
    with col_wt:
        weapon_type = st.radio(
            "Weapon Type", ["one-handed", "two-handed"],
            format_func=lambda x: x.title(),
            horizontal=True, key="be_wm_weapon_type",
        )
    with col_awk:
        awakening = st.number_input(
            "Enchant Awakening Level", min_value=0, max_value=max_awakening,
            step=1, key="be_wm_awakening",
            help=f"Max awakening based on your enchant levels: {max_awakening}",
        )

    awk_info = get_enchant_awakening_info(awakening)
    st.caption(
        f"Required enchant level for this awakening: **{awk_info['enchant_lvl']}**  ·  "
        f"Modifier: **×{awk_info['modifier']:.1f}**  ·  "
        f"Max awakening available: **{max_awakening}**"
    )

    all_stat_names = ["None"] + list(ENCHANT_STAT_FIELD_MAP.keys())

    def _enchant_slot_row(prefix: str, i: int, wtype: str) -> dict | None:
        col_s, col_l, col_q, col_c = st.columns([3, 1, 2, 2])
        with col_s:
            stat = st.selectbox(
                f"Slot {i + 1}", all_stat_names,
                key=f"{prefix}_{i}_stat", label_visibility="collapsed",
            )
        with col_l:
            lvl = st.number_input(
                "Level", min_value=1, max_value=20, step=1,
                key=f"{prefix}_{i}_lvl", label_visibility="collapsed",
                disabled=(stat == "None"),
            )
        with col_q:
            qual = st.selectbox(
                "Quality", QUALITY_OPTIONS,
                key=f"{prefix}_{i}_qual", label_visibility="collapsed",
                disabled=(stat == "None"),
            )

        city = None
        if stat != "None":
            cities = get_enchant_cities_for_stat(wtype, stat)
            with col_c:
                if len(cities) > 1:
                    saved = st.session_state.get(f"{prefix}_{i}_city")
                    cur_city = saved if saved in cities else cities[0]
                    city = st.selectbox(
                        "City", cities,
                        index=cities.index(cur_city),
                        key=f"{prefix}_{i}_city",
                        label_visibility="collapsed",
                    )
                elif cities:
                    city = cities[0]
                    st.session_state[f"{prefix}_{i}_city"] = city
                    st.caption(city)

            opts = get_weapon_enchant_options(wtype, lvl, qual, awk_info["modifier"], city=city)
            opt_map = {o["stat_en"]: o for o in opts}
            if stat in opt_map:
                raw = opt_map[stat]["raw_value"]
                eff = opt_map[stat]["effective_value"]
                modifier = awk_info["modifier"]
                if modifier > 1.0:
                    bonus = round(eff - raw, 4)
                    st.caption(
                        f"+{raw:g} base  +  +{bonus:g} awakening  =  **+{eff:g}**  "
                        f"({ENCHANT_STAT_LABELS.get(stat, stat)})"
                    )
                else:
                    st.caption(f"+{eff:g}  ({ENCHANT_STAT_LABELS.get(stat, stat)})")
            return {"stat_en": stat, "quality": qual, "city": city, "level": lvl}
        return None

    # Weapon enchants
    st.divider()
    st.markdown("**Weapon Enchants**")
    col_hdr_s, col_hdr_l, col_hdr_q, col_hdr_c = st.columns([3, 1, 2, 2])
    with col_hdr_s:
        st.caption("Stat")
    with col_hdr_l:
        st.caption("Lvl")
    with col_hdr_q:
        st.caption("Quality")
    with col_hdr_c:
        st.caption("City")

    st.markdown("**Main Weapon**")
    main_enchants = [_enchant_slot_row("be_wm_main", i, weapon_type) for i in range(3)]

    sub_enchants: list[dict | None] = [None, None, None]
    if weapon_type == "one-handed":
        st.markdown("**Sub-Weapon**")
        sub_enchants = [_enchant_slot_row("be_wm_sub", i, "sub") for i in range(3)]

    # Armor enchants
    st.divider()
    st.markdown("**Armor Enchants**")
    st.caption("*Work in progress — armor enchant tracking coming soon.*")

    # Accessory enchants
    st.divider()
    st.markdown("**Accessory Enchants**")
    st.caption("*Work in progress — accessory enchant tracking coming soon.*")

# ── Tab 3: Cards ──────────────────────────────────────────────────────────
with tab_cards:
    drake_card = st.toggle(
        "Drake Card",
        key="be_wm_drake_card",
        help=(
            "Drake Card: removes the size modifier from damage calculations. "
            "The size multiplier is treated as ×1.0 regardless of weapon type or size bonuses."
        ),
    )

weapon_meta = {
    "weapon_type":           st.session_state.get("be_wm_weapon_type",           "one-handed"),
    "weapon_enchant_lvl":    st.session_state.get("be_wm_weapon_enchant_lvl",    0),
    "armor_enchant_lvl":     st.session_state.get("be_wm_armor_enchant_lvl",     0),
    "accessory_enchant_lvl": st.session_state.get("be_wm_accessory_enchant_lvl", 0),
    "enchant_awakening":     st.session_state.get("be_wm_awakening",             0),
    "main_enchants":         main_enchants,
    "sub_enchants":          sub_enchants,
    "drake_card":            st.session_state.get("be_wm_drake_card",            False),
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
            try:
                save_build(name, off_vals, def_vals, weapon_meta)
            except ValueError as exc:
                st.error(str(exc))
                st.stop()
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