"""
DMG Calculator
--------------
Select offensive and target builds, configure mode / damage type / attack type,
and calculate total damage. Supports multi-build comparison.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
import plotly.graph_objects as go

from build_store import (
    OFFENSIVE_FIELDS,
    PCT_FIELDS, SELECT_FIELDS,
    init_store, get_builds,
    get_build_offensive, get_build_defensive,
    calculate, render_sidebar,
)

st.set_page_config(page_title="DMG Calculator", layout="wide")
render_sidebar()

st.title("DMG Calculator")
st.caption(
    "Select one or more offensive builds and a target build, then configure the "
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
    st.markdown("**Target Build**")
    sel_def = st.selectbox(
        "Select target build", options=build_names,
        key="dc_def_build", label_visibility="collapsed",
    )

if not sel_off:
    st.info("Select at least one offensive build above.")
    st.stop()

# ---------------------------------------------------------------------------
# Calculation
# ---------------------------------------------------------------------------
dmg_type_param = "pen" if dmg_type == "Penetration" else "crit"
attack_mult    = 16 if _is_skill else 8
_pmatk         = pmatk_pct if _is_skill else 100
_hits          = num_hits if _is_skill else 1

def_raw = get_build_defensive(sel_def)

results: dict[str, float] = {}
for bname in sel_off:
    off_raw = dict(get_build_offensive(bname))
    off_raw['patk'] = off_raw['patk'] * _pmatk / 100
    results[bname] = calculate(mode, off_raw, def_raw, dmg_type_param, attack_mult) * _hits

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
atk_label = atk_type + (f"  ·  {_hits} hit{'s' if _hits != 1 else ''}" if _hits > 1 else "")

if len(sel_off) == 1:
    # ── Markdown card ──────────────────────────────────────────────────────
    bname = sel_off[0]
    mult  = results[bname]
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(231,76,60,0.15) 0%, rgba(26,26,46,0.6) 100%);
                border: 1px solid rgba(231,76,60,0.5); border-radius: 12px;
                padding: 20px 32px; text-align: center; margin: 16px 0;">
        <div style="font-size: 12px; color: #aaa; letter-spacing: 2px;
                    text-transform: uppercase; margin-bottom: 4px;">
            {mode}  ·  {dmg_type}  ·  {atk_label}
        </div>
        <div style="font-size: 14px; color: #ccc; margin-bottom: 2px;">{bname}  vs  {sel_def}</div>
        <div style="font-size: 56px; font-weight: 800; color: #e74c3c; line-height: 1.1;">
            {mult:,.2f}
        </div>
        <div style="font-size: 12px; color: #888; margin-top: 4px;">Damage Multiplier</div>
    </div>
    """, unsafe_allow_html=True)

else:
    # ── Bar chart ──────────────────────────────────────────────────────────
    sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
    names  = [k for k, _ in sorted_results]
    values = [v for _, v in sorted_results]
    max_v  = max(values)

    def _gradient_colors(vals):
        anchors = [(1.0, (255, 215, 0)), (0.5, (46, 204, 113)), (0.0, (93, 173, 226))]
        colors = []
        for v in vals:
            v = max(0.0, min(1.0, v))
            color = (93, 173, 226)
            for i in range(len(anchors) - 1):
                hi_v, hi_c = anchors[i]
                lo_v, lo_c = anchors[i + 1]
                if v >= lo_v:
                    t = (v - lo_v) / (hi_v - lo_v) if hi_v != lo_v else 1.0
                    color = tuple(int(lo_c[j] + t * (hi_c[j] - lo_c[j])) for j in range(3))
                    break
            colors.append(f'#{color[0]:02x}{color[1]:02x}{color[2]:02x}')
        return colors

    colors = _gradient_colors([v / max_v for v in values])

    fig = go.Figure(go.Bar(
        x=values, y=names, orientation='h',
        marker=dict(color=colors, line=dict(width=0)),
        text=[f"{v:,.2f}" for v in values],
        textposition='outside',
        textfont=dict(size=11),
        hovertemplate='<b>%{y}</b><br>Multiplier: %{x:,.2f}<extra></extra>',
    ))
    fig.update_layout(
        title=dict(
            text=f"{mode}  ·  {dmg_type}  ·  {atk_label}  ·  vs {sel_def}",
            font=dict(size=13), x=0,
        ),
        xaxis=dict(title="Damage Multiplier", showgrid=False, zeroline=False, showline=False),
        yaxis=dict(autorange='reversed', showgrid=False, tickfont=dict(size=12)),
        margin=dict(l=0, r=80, t=40, b=40),
        height=80 + 40 * len(values),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
    )
    st.plotly_chart(fig, use_container_width=True)
