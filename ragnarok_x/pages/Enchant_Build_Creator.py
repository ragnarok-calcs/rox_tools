"""
Enchant Build Creator
---------------------
Create a new build by selecting weapon, armor, and accessory enchants.
The selected enchants are interpreted into build stats and saved as a standard build.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
from build_store import (
    OFFENSIVE_FIELDS, DEFENSIVE_FIELDS, FLOAT_PCT_FIELDS,
    init_store, save_build, render_sidebar, render_stats_panel,
)
from data.enchants_data import (
    ARMOR_STAT_FIELD_MAP, ACCESSORY_STAT_FIELD_MAP,
    ARMOR_EQUIP_LABEL, ACCESSORY_EQUIP_LABEL,
    ENCHANT_STAT_FIELD_MAP, WEAPON_EQUIP_LABEL,
    get_enchant_cities_by_equip, get_enchant_quality_values_by_equip,
    get_max_awakening_for_enchant_levels, get_enchant_awakening_info,
)

st.set_page_config(page_title="Build Creator — From Enchants", layout="wide")

render_sidebar()

st.title("Build Creator — From Enchants")
st.caption("Select your weapon, armor, and accessory enchants to automatically derive build stats.")

init_store()

# ── Enchant parameters ─────────────────────────────────────────────────────
for _lvl_key in ("be_fe_weapon_lvl", "be_fe_armor_lvl", "be_fe_accessory_lvl"):
    if _lvl_key not in st.session_state:
        st.session_state[_lvl_key] = 20

st.markdown("**Enchant Parameters**")
col_wt, col_wlvl, col_alvl, col_aclvl = st.columns(4)
with col_wt:
    fe_weapon_type = st.radio(
        "Weapon Type", ["one-handed", "two-handed", "dagger"],
        format_func=lambda x: x.title(),
        horizontal=True, key="be_fe_weapon_type",
    )
with col_wlvl:
    fe_weapon_lvl = st.number_input(
        "Weapon Enchant Level", min_value=0, max_value=20, step=1,
        key="be_fe_weapon_lvl",
        help="Enchant level applied to the weapon (0–20).",
    )
with col_alvl:
    fe_armor_lvl = st.number_input(
        "Armor Enchant Level", min_value=0, max_value=20, step=1,
        key="be_fe_armor_lvl",
        help="Enchant level applied to all armor pieces (0–20).",
    )
with col_aclvl:
    fe_acc_lvl = st.number_input(
        "Accessory Enchant Level", min_value=0, max_value=20, step=1,
        key="be_fe_accessory_lvl",
        help="Enchant level applied to all accessories (0–20).",
    )

fe_max_awk = get_max_awakening_for_enchant_levels(fe_weapon_lvl, fe_armor_lvl, fe_acc_lvl)
if st.session_state.get("be_fe_awakening", 0) > fe_max_awk:
    st.session_state["be_fe_awakening"] = fe_max_awk

fe_awakening = st.number_input(
    "Enchant Awakening Level", min_value=0, max_value=fe_max_awk,
    step=1, key="be_fe_awakening",
    help=f"Max awakening based on your enchant levels: {fe_max_awk}",
)
fe_awk_info = get_enchant_awakening_info(fe_awakening)
st.caption(
    f"Modifier: **×{fe_awk_info['modifier']:.1f}**  ·  "
    f"Max awakening available: **{fe_max_awk}**"
)

# ── Slot row helpers ───────────────────────────────────────────────────────
_QUALITY_ORDER = ["White", "Blue", "Purple", "Orange"]
_QUALITY_ICONS = {"White": "⬜", "Blue": "🔵", "Purple": "🟣", "Orange": "🟡"}


def _slot_row(prefix: str, i: int, equip_label: str, stat_map: dict, default_lvl: int) -> dict | None:
    all_stats = ["None"] + list(stat_map.keys())
    col_s, col_l, col_c, col_q = st.columns([3, 1, 2, 2])
    with col_s:
        stat = st.selectbox(
            f"Slot {i + 1}", all_stats,
            key=f"{prefix}_{i}_stat", label_visibility="collapsed",
        )
    lvl_key = f"{prefix}_{i}_lvl"
    if lvl_key not in st.session_state:
        st.session_state[lvl_key] = max(1, default_lvl)
    with col_l:
        lvl = st.number_input(
            "Level", min_value=1, max_value=20, step=1,
            key=lvl_key, label_visibility="collapsed",
            disabled=(stat == "None"),
        )

    city = None
    qual = st.session_state.get(f"{prefix}_{i}_qual", "Orange")

    if stat != "None":
        cities = get_enchant_cities_by_equip(equip_label, stat)
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

        qual_vals = get_enchant_quality_values_by_equip(
            equip_label, lvl, stat, fe_awk_info["modifier"], city=city,
        )
        if qual_vals:
            available_quals = [q for q in _QUALITY_ORDER if q in qual_vals]
            if qual not in available_quals:
                qual = available_quals[-1]
                st.session_state[f"{prefix}_{i}_qual"] = qual

            _mod = fe_awk_info["modifier"]
            if _mod > 1.0:
                def _fmt(q, _v=qual_vals, _m=_mod, _ic=_QUALITY_ICONS):
                    raw   = round(_v[q] / _m, 4)
                    bonus = round(_v[q] - raw, 4)
                    return f"{_ic[q]}  +{raw:g} (base)  +{bonus:g} (awakening)"
            else:
                def _fmt(q, _v=qual_vals, _ic=_QUALITY_ICONS):
                    return f"{_ic[q]}  +{_v[q]:g}"

            with col_q:
                qual = st.selectbox(
                    f"Quality slot {i + 1}",
                    options=available_quals,
                    format_func=_fmt,
                    key=f"{prefix}_{i}_qual",
                    label_visibility="collapsed",
                )
        else:
            st.caption("⚠️ No values found.")

        return {"stat_en": stat, "quality": qual, "city": city, "level": lvl}
    return None


def _piece_section(label: str, prefix: str, equip_label: str, stat_map: dict, default_lvl: int) -> list:
    st.markdown(f"**{label}**")
    col_h_s, col_h_l, col_h_c, col_h_q = st.columns([3, 1, 2, 2])
    with col_h_s: st.caption("Stat")
    with col_h_l: st.caption("Lvl")
    with col_h_c: st.caption("City")
    with col_h_q: st.caption("Value")
    return [_slot_row(prefix, i, equip_label, stat_map, default_lvl) for i in range(3)]


# ── Weapon enchants ────────────────────────────────────────────────────────
st.divider()
st.markdown("**Weapon Enchants**")
main_equip_label = WEAPON_EQUIP_LABEL[fe_weapon_type]
fe_main_slots: list[dict | None] = list(
    _piece_section("Main Weapon", "be_fe_main", main_equip_label, ENCHANT_STAT_FIELD_MAP, fe_weapon_lvl)
)

fe_sub_slots: list[dict | None] = [None, None, None]
if fe_weapon_type == "one-handed":
    fe_sub_slots = list(
        _piece_section("Sub-Weapon", "be_fe_sub", WEAPON_EQUIP_LABEL["sub"], ENCHANT_STAT_FIELD_MAP, fe_weapon_lvl)
    )
elif fe_weapon_type == "dagger":
    fe_sub_slots = list(
        _piece_section("Off-hand Dagger", "be_fe_sub", WEAPON_EQUIP_LABEL["dagger"], ENCHANT_STAT_FIELD_MAP, fe_weapon_lvl)
    )

# ── Armor pieces ───────────────────────────────────────────────────────────
st.divider()
st.markdown("**Armor Enchants**")
fe_armor_slots: list[dict | None] = []
for _piece_lbl, _piece_pfx in [
    ("Clothes", "be_fe_armor_clothes"),
    ("Cloak",   "be_fe_armor_cloak"),
    ("Boots",   "be_fe_armor_boots"),
]:
    fe_armor_slots.extend(_piece_section(_piece_lbl, _piece_pfx, ARMOR_EQUIP_LABEL, ARMOR_STAT_FIELD_MAP, fe_armor_lvl))

# ── Accessory pieces ───────────────────────────────────────────────────────
st.divider()
st.markdown("**Accessory Enchants**")
fe_acc_slots: list[dict | None] = []
for _piece_lbl, _piece_pfx in [
    ("Decoration 1", "be_fe_acc_deco1"),
    ("Decoration 2", "be_fe_acc_deco2"),
    ("Talisman",     "be_fe_acc_talisman"),
]:
    fe_acc_slots.extend(_piece_section(_piece_lbl, _piece_pfx, ACCESSORY_EQUIP_LABEL, ACCESSORY_STAT_FIELD_MAP, fe_acc_lvl))

# ── Compute stats from selected enchants ───────────────────────────────────
fe_off_acc = {f: float(dflt) for f, (_, dflt) in OFFENSIVE_FIELDS.items()}
fe_def_acc = {f: float(dflt) for f, (_, dflt) in DEFENSIVE_FIELDS.items()}

for _slot, _smap, _elabel in (
    [(s, ENCHANT_STAT_FIELD_MAP,   main_equip_label)       for s in fe_main_slots  if s] +
    [(s, ENCHANT_STAT_FIELD_MAP,   WEAPON_EQUIP_LABEL["sub"]) for s in fe_sub_slots if s] +
    [(s, ARMOR_STAT_FIELD_MAP,     ARMOR_EQUIP_LABEL)      for s in fe_armor_slots  if s] +
    [(s, ACCESSORY_STAT_FIELD_MAP, ACCESSORY_EQUIP_LABEL)  for s in fe_acc_slots    if s]
):
    _field = _smap.get(_slot["stat_en"])
    if not _field:
        continue
    _qvals = get_enchant_quality_values_by_equip(
        _elabel, _slot["level"], _slot["stat_en"], fe_awk_info["modifier"], city=_slot.get("city")
    )
    _val = _qvals.get(_slot["quality"], 0.0)
    if _field in fe_off_acc:
        fe_off_acc[_field] += _val
    elif _field in fe_def_acc:
        fe_def_acc[_field] += _val

fe_off_final: dict = {}
for f, v in fe_off_acc.items():
    fe_off_final[f] = round(v, 2) if f in FLOAT_PCT_FIELDS else int(round(v))

fe_def_final: dict = {}
for f, v in fe_def_acc.items():
    fe_def_final[f] = round(v, 2) if f in FLOAT_PCT_FIELDS else int(round(v))

# ── Floating stats panel ───────────────────────────────────────────────────
render_stats_panel(fe_off_final, fe_def_final)

# ── Full stat sheet (detail review before saving) ──────────────────────────
st.divider()
with st.expander("Full stat sheet", expanded=False):
    col_full_off, col_full_def = st.columns(2)
    with col_full_off:
        for f, (lbl, _) in OFFENSIVE_FIELDS.items():
            st.text(f"{lbl}: {fe_off_final[f]}")
    with col_full_def:
        for f, (lbl, _) in DEFENSIVE_FIELDS.items():
            st.text(f"{lbl}: {fe_def_final[f]}")

# ── Save ───────────────────────────────────────────────────────────────────
st.divider()
fe_build_name = st.text_input(
    "Build name", key="be_fe_build_name",
    placeholder="Enter a name for this build",
)
fe_weapon_meta = {
    "weapon_type":           fe_weapon_type,
    "weapon_enchant_lvl":    fe_weapon_lvl,
    "armor_enchant_lvl":     fe_armor_lvl,
    "accessory_enchant_lvl": fe_acc_lvl,
    "enchant_awakening":     fe_awakening,
    "main_enchants":         fe_main_slots,
    "sub_enchants":          fe_sub_slots,
    "drake_card":            False,
}
if st.button("💾 Create Build from Enchants", type="primary", key="be_fe_save"):
    _fe_name = fe_build_name.strip()
    if not _fe_name:
        st.error("Enter a build name.")
    else:
        try:
            save_build(_fe_name, fe_off_final, fe_def_final, fe_weapon_meta)
        except ValueError as exc:
            st.error(str(exc))
            st.stop()
        st.toast(f"Build '{_fe_name}' created from enchants!", icon="✅")
        st.rerun()
