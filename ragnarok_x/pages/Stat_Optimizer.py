"""
Stat Optimization
-----------------
Select one offensive build and one target build. Reports effective multipliers
per stat group and a ranked stat priority breakdown.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st

from build_store import (
    OFFENSIVE_FIELDS, DEFENSIVE_FIELDS,
    PCT_FIELDS, SELECT_FIELDS, EDITOR_GROUPS,
    init_store, get_builds,
    get_build_offensive, get_build_defensive,
    get_weights, render_sidebar,
)

st.set_page_config(page_title="Stat Optimization", layout="wide")
render_sidebar()

st.title("Stat Optimization")
st.caption(
    "Select an offensive build and a target build to see effective multipliers per "
    "stat group and a ranked breakdown of stat investment priority."
)

init_store()
builds = get_builds()
build_names = list(builds.keys())

if not build_names:
    st.info("No builds saved yet. Create one in the **Build Editor** page.")
    st.stop()

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------
col_mode, col_dmg, col_atk = st.columns([1, 2, 2])
with col_mode:
    mode = st.radio("Mode", ["PVE", "PVP"], horizontal=True, key="so_mode")
with col_dmg:
    dmg_type = st.radio(
        "Damage Type", ["Crit", "Penetration"], horizontal=True, key="so_dmg_type",
        help="Crit or Penetration — affects which ATK multiplier is used.",
    )
with col_atk:
    atk_type = st.radio(
        "Attack Type", ["Normal Attack", "Skill Attack"], horizontal=True, key="so_atk_type",
    )

_is_skill = atk_type == "Skill Attack"
col_pmatk, col_hits, _ = st.columns([1, 1, 4])
with col_pmatk:
    pmatk_pct = st.number_input(
        "P/MATK% Modifier", min_value=0, max_value=99999, value=100, step=1,
        key="so_pmatk_pct", disabled=not _is_skill,
    )
with col_hits:
    num_hits = st.number_input(
        "Number of Hits", min_value=1, max_value=99, value=1, step=1,
        key="so_num_hits", disabled=not _is_skill,
    )

st.divider()

# ---------------------------------------------------------------------------
# Build selection
# ---------------------------------------------------------------------------
col_off, col_def = st.columns(2)
with col_off:
    st.markdown("**Offensive Build**")
    sel_off = st.selectbox("Select offensive build", options=build_names,
                            key="so_off_build", label_visibility="collapsed")
with col_def:
    st.markdown("**Target Build**")
    sel_def = st.selectbox("Select target build", options=build_names,
                            key="so_def_build", label_visibility="collapsed")

st.divider()

# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------
dmg_type_param = "pen" if dmg_type == "Penetration" else "crit"
attack_mult    = 16 if _is_skill else 8
_pmatk         = pmatk_pct if _is_skill else 100

off_raw = dict(get_build_offensive(sel_off))
off_raw['patk'] = off_raw['patk'] * _pmatk / 100
def_raw = get_build_defensive(sel_def)

weights = get_weights(mode, off_raw, def_raw, dmg_type_param, attack_mult)

# Remove inactive damage-type stat
if dmg_type_param == "crit":
    weights.pop('total_final_pen', None)
else:
    weights.pop('crit_dmg_bonus', None)

# Remove static select fields and zero/negative weights for priority display
weights = {k: v for k, v in weights.items() if k not in SELECT_FIELDS}
positive_weights = {k: v for k, v in weights.items() if v > 0}

labels_map = {f: label for f, (label, _) in OFFENSIVE_FIELDS.items()}

# ---------------------------------------------------------------------------
# Effective multipliers per group
# ---------------------------------------------------------------------------
st.markdown("#### Effective Multipliers by Group")
st.caption("Shows the net multiplicative factor each stat group contributes to the damage formula.")

eff_cols = st.columns(4)
col_idx = 0

_skip_grp = "Penetration" if dmg_type_param == "crit" else "Crit"
for grp_label, icon, off_keys, def_keys, eff_pve, eff_pvp in EDITOR_GROUPS:
    if grp_label == _skip_grp:
        continue
    eff_fn = eff_pve if mode == "PVE" else eff_pvp
    if eff_fn is None:
        continue

    o_vals = {f: off_raw.get(f, OFFENSIVE_FIELDS[f][1]) for f in off_keys}
    d_vals = {f: def_raw.get(f, DEFENSIVE_FIELDS[f][1]) for f in def_keys}
    try:
        eff = eff_fn(o_vals, d_vals)
    except Exception:
        continue

    with eff_cols[col_idx % 4]:
        color = "#2ecc71" if eff >= 1.0 else "#e74c3c"
        st.markdown(f"""
        <div style="background:rgba(255,255,255,0.05); border-radius:8px;
                    padding:12px 14px; margin-bottom:10px; text-align:center;">
            <div style="font-size:11px; color:#888; text-transform:uppercase;
                        letter-spacing:1px; margin-bottom:4px;">{icon} {grp_label}</div>
            <div style="font-size:28px; font-weight:700; color:{color};">{eff:.3f}×</div>
        </div>
        """, unsafe_allow_html=True)
    col_idx += 1

st.divider()

# ---------------------------------------------------------------------------
# Stat priority
# ---------------------------------------------------------------------------
st.markdown("#### Stat Priority")
st.caption(
    "Bars show relative priority vs the selected reference stat (★). "
    "Score is normalized so the best stat = 1.00. "
    "Equivalence shows how many points of each stat equal 1 point of the reference."
)

if not positive_weights:
    st.warning("No positive-weight stats found for the current configuration.")
    st.stop()

best_stat = max(positive_weights, key=positive_weights.get)

st.markdown(f"""
<div style="background: rgba(46,204,113,0.1); border-left: 3px solid #2ecc71;
            border-radius: 0 6px 6px 0; padding: 8px 14px; margin-bottom: 12px;">
    <span style="color:#2ecc71; font-weight:700;">▲ Top priority: {labels_map[best_stat]}</span>
    <span style="color:#aaa; font-size:13px;"> — invest here for the greatest DPS gain per point.</span>
</div>
""", unsafe_allow_html=True)

ref_options = sorted(positive_weights.keys(), key=lambda k: labels_map[k])
current_ref = st.session_state.get("so_ref", best_stat)
if current_ref not in ref_options:
    current_ref = best_stat
reference = st.selectbox(
    "Reference stat for equivalence", options=ref_options,
    format_func=lambda k: labels_map[k],
    index=ref_options.index(current_ref),
    key="so_ref",
)

# Render priority table
ref_w  = positive_weights[reference]
max_w  = max(positive_weights.values())
sorted_items = sorted(positive_weights.items(), key=lambda x: x[1], reverse=True)
ref_label = labels_map[reference]

header_html = f"""
<div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;
            padding-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.15);
            color:#888; font-size:11px; text-transform:uppercase; letter-spacing:1px;">
    <div style="width:26px; flex-shrink:0;"></div>
    <div style="flex:2;">Stat</div>
    <div style="flex:3;">Relative Priority</div>
    <div style="flex:1; text-align:right; padding-right:8px;">Score</div>
    <div style="flex:1; text-align:right;">Per 1 {ref_label}</div>
</div>
"""
rows_html = ""
for rank, (field, w) in enumerate(sorted_items):
    label    = labels_map[field]
    is_ref   = field == reference
    norm     = w / max_w
    equiv    = ref_w / w
    if rank == 0:
        bg, fg = '#FFD700', '#1a1a1a'
    elif rank <= 2:
        bg, fg = '#2ecc71', '#ffffff'
    else:
        bg, fg = '#5dade2', '#ffffff'
    bar_w  = int(norm * 100)
    n_sty  = "font-weight:700;" if is_ref else ""
    star   = " ★" if is_ref else ""
    eq_str = "1.00" if is_ref else f"{equiv:.2f}"
    rows_html += f"""
    <div style="display:flex; align-items:center; gap:8px; margin-bottom:7px;">
        <div style="background:{bg}; color:{fg}; border-radius:50%;
                    width:26px; height:26px; display:flex; align-items:center;
                    justify-content:center; font-size:11px; font-weight:700; flex-shrink:0;">
            {rank + 1}
        </div>
        <div style="flex:2; font-size:13px; {n_sty}">{label}{star}</div>
        <div style="flex:3; background:rgba(255,255,255,0.08); border-radius:4px; height:14px; overflow:hidden;">
            <div style="width:{bar_w}%; height:100%; background:{bg}; border-radius:4px;"></div>
        </div>
        <div style="flex:1; text-align:right; font-family:monospace; font-size:13px;
                    color:#ccc; padding-right:8px;">{norm:.2f}</div>
        <div style="flex:1; text-align:right; font-family:monospace; font-size:13px; color:#aaa;">
            {eq_str}
        </div>
    </div>
    """

st.html(header_html + rows_html)
