"""
DMG Calculator
--------------
Select offensive and target builds, configure mode / damage type / attack type,
and calculate total damage. Supports many:many build comparison.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st

from build_store import (
    OFFENSIVE_FIELDS,
    PCT_FIELDS, SCENARIO_SELECT_FIELDS,
    init_store, get_builds,
    get_build_offensive, get_build_defensive, get_build_weapon_meta,
    apply_card_effects, calculate, render_sidebar, render_inline_build_editor,
)

st.set_page_config(page_title="DMG Calculator", layout="wide")
render_sidebar()

st.title("DMG Calculator")
st.caption(
    "Select one or more offensive builds and one or more target builds, then configure the "
    "calculation parameters to see damage output."
)

init_store()
builds = get_builds()
build_names = list(builds.keys())

if not build_names:
    st.info("No builds saved yet. Create one in the **Build Editor** page.")
    st.stop()

# ---------------------------------------------------------------------------
# Calculation parameters
# ---------------------------------------------------------------------------
col_mode, col_dmg, col_atk = st.columns([1, 2, 2])
with col_mode:
    mode = st.radio("Mode", ["PVE", "PVP"], horizontal=True, key="dc_mode")
with col_dmg:
    dmg_type = st.radio(
        "Damage Type", ["Crit", "Penetration"], horizontal=True, key="dc_dmg_type",
        help=(
            "Crit: multiplied by (Crit DMG Bonus − Crit DMG Reduc).  "
            "Penetration: non-crit, multiplier = 1 + PEN−DEF (or 1 + 2×(PEN−DEF) − 1.5 if diff > 1.5)."
        ),
    )
with col_atk:
    atk_type = st.radio(
        "Attack Type", ["Normal Attack", "Skill Attack"], horizontal=True, key="dc_atk_type",
        help="Normal: attack_mult=8, P/MATK%=100, hits=1.  Skill: attack_mult=16, user-defined.",
    )

_is_skill = atk_type == "Skill Attack"
col_size, col_elem, _ = st.columns([1, 2, 3])
with col_size:
    weapon_size_modifier = st.selectbox(
        "Weapon Size", options=SCENARIO_SELECT_FIELDS['weapon_size_modifier'],
        format_func=lambda x: f"{x}%",
        index=SCENARIO_SELECT_FIELDS['weapon_size_modifier'].index(100),
        key="dc_weapon_size_modifier",
    )
with col_elem:
    elemental_counter = st.selectbox(
        "Elemental Counter", options=SCENARIO_SELECT_FIELDS['elemental_counter'],
        format_func=lambda x: f"{x}%",
        index=SCENARIO_SELECT_FIELDS['elemental_counter'].index(100),
        key="dc_elemental_counter",
    )
col_pmatk, col_hits, _ = st.columns([1, 1, 4])
with col_pmatk:
    pmatk_pct = st.number_input(
        "P/MATK% Modifier", min_value=0, max_value=99999, value=100, step=1,
        key="dc_pmatk_pct", disabled=not _is_skill,
        help="Skill P/MATK% applied to P.ATK in the base formula (100 = 1×).",
    )
with col_hits:
    num_hits = st.number_input(
        "Number of Hits", min_value=1, max_value=99, value=1, step=1,
        key="dc_num_hits", disabled=not _is_skill,
        help="How many times the skill hits. Final damage = single-hit × hits.",
    )

st.divider()

# ---------------------------------------------------------------------------
# Build selection
# ---------------------------------------------------------------------------
col_off, col_def = st.columns(2)
with col_off:
    st.markdown("**Offensive Builds**")
    sel_off = st.multiselect(
        "Select one or more offensive builds", options=build_names,
        key="dc_off_builds", label_visibility="collapsed",
    )
with col_def:
    st.markdown("**Target Builds**")
    sel_def = st.multiselect(
        "Select one or more target builds", options=build_names,
        key="dc_def_builds", label_visibility="collapsed",
    )

if not sel_off or not sel_def:
    st.info("Select at least one offensive build and one target build above.")
    st.stop()

# ── Inline build editor (single offensive build selected) ─────────────────
if len(sel_off) == 1:
    render_inline_build_editor(sel_off[0], kp="dc")

# ---------------------------------------------------------------------------
# Calculation
# ---------------------------------------------------------------------------
dmg_type_param = "pen" if dmg_type == "Penetration" else "crit"
attack_mult    = 16 if _is_skill else 8
_pmatk         = pmatk_pct if _is_skill else 100
_hits          = num_hits if _is_skill else 1

# results[off_name][def_name] = damage
results: dict[str, dict[str, float]] = {}
for off_name in sel_off:
    base_off_raw = dict(get_build_offensive(off_name))
    base_off_raw['weapon_size_modifier'] = weapon_size_modifier
    base_off_raw['elemental_counter']    = elemental_counter
    wm = get_build_weapon_meta(off_name)
    results[off_name] = {}
    for def_name in sel_def:
        def_raw = get_build_defensive(def_name)
        off_raw, eff_def_raw = apply_card_effects(base_off_raw, def_raw, wm)
        off_raw = dict(off_raw)
        off_raw['patk'] = off_raw['patk'] * _pmatk / 100
        results[off_name][def_name] = (
            calculate(mode, off_raw, eff_def_raw, dmg_type_param, attack_mult) * _hits
        )

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
atk_label = atk_type + (f"  ·  {_hits} hit{'s' if _hits != 1 else ''}" if _hits > 1 else "")

if len(sel_off) == 1 and len(sel_def) == 1:
    # ── Single card ──────────────────────────────────────────────────────
    off_name = sel_off[0]
    def_name = sel_def[0]
    mult = results[off_name][def_name]
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(231,76,60,0.15) 0%, rgba(26,26,46,0.6) 100%);
                border: 1px solid rgba(231,76,60,0.5); border-radius: 12px;
                padding: 20px 32px; text-align: center; margin: 16px 0;">
        <div style="font-size: 12px; color: #aaa; letter-spacing: 2px;
                    text-transform: uppercase; margin-bottom: 4px;">
            {mode}  ·  {dmg_type}  ·  {atk_label}
        </div>
        <div style="font-size: 14px; color: #ccc; margin-bottom: 2px;">{off_name}  vs  {def_name}</div>
        <div style="font-size: 56px; font-weight: 800; color: #e74c3c; line-height: 1.1;">
            {mult:,.2f}
        </div>
        <div style="font-size: 12px; color: #888; margin-top: 4px;">Damage Multiplier</div>
    </div>
    """, unsafe_allow_html=True)

else:
    # ── HTML bar readout ──────────────────────────────────────────────────
    # Compute mean per offensive build; sort groups by mean descending
    means = {
        off: sum(results[off].values()) / len(results[off])
        for off in sel_off
    }
    sorted_off = sorted(sel_off, key=lambda o: means[o], reverse=True)

    # Normalise all bars against the highest individual damage value
    max_val = max(v for off in results.values() for v in off.values())

    header_html = """
<div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;
            padding-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.15);
            color:#888; font-size:11px; text-transform:uppercase; letter-spacing:1px;">
    <div style="width:26px; flex-shrink:0;"></div>
    <div style="flex:2;">Offensive Build</div>
    <div style="flex:3;">Damage Output</div>
    <div style="flex:1; text-align:right;">Multiplier</div>
</div>
"""

    rows_html = ""
    for rank, off_name in enumerate(sorted_off):
        mean_val = means[off_name]
        norm     = mean_val / max_val

        if rank == 0:
            bg, fg = '#FFD700', '#1a1a1a'
        elif rank <= 2:
            bg, fg = '#2ecc71', '#ffffff'
        else:
            bg, fg = '#5dade2', '#ffffff'

        bar_w = int(norm * 100)

        rows_html += f"""
<div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
    <div style="background:{bg}; color:{fg}; border-radius:50%;
                width:26px; height:26px; display:flex; align-items:center;
                justify-content:center; font-size:11px; font-weight:700; flex-shrink:0;">
        {rank + 1}
    </div>
    <div style="flex:2; font-size:13px; font-weight:700;">{off_name}</div>
    <div style="flex:3; background:rgba(255,255,255,0.08); border-radius:4px; height:14px; overflow:hidden;">
        <div style="width:{bar_w}%; height:100%; background:{bg}; border-radius:4px;"></div>
    </div>
    <div style="flex:1; text-align:right; font-family:monospace; font-size:13px; color:#ccc;">
        {mean_val:,.2f}
    </div>
</div>
"""
        # Sub-bars: one per target build, normalised to the same max
        for def_name in sel_def:
            sub_val  = results[off_name][def_name]
            sub_norm = sub_val / max_val
            sub_w    = int(sub_norm * 100)
            rows_html += f"""
<div style="display:flex; align-items:center; gap:8px; margin-bottom:3px; padding-left:34px; opacity:0.65;">
    <div style="flex:2; font-size:11px; color:#aaa; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{def_name}</div>
    <div style="flex:3; background:rgba(255,255,255,0.05); border-radius:3px; height:7px; overflow:hidden;">
        <div style="width:{sub_w}%; height:100%; background:{bg}; border-radius:3px; opacity:0.6;"></div>
    </div>
    <div style="flex:1; text-align:right; font-family:monospace; font-size:11px; color:#888;">{sub_val:,.2f}</div>
</div>
"""
        rows_html += '<div style="margin-bottom:10px;"></div>'

    st.html(header_html + rows_html)
