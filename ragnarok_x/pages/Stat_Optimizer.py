"""
Stat Optimization
-----------------
Select one offensive build and one or more target builds. Reports effective multipliers
per stat group and a ranked stat priority breakdown.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st

from build_store import (
    OFFENSIVE_FIELDS, DEFENSIVE_FIELDS,
    PCT_FIELDS, SCENARIO_SELECT_FIELDS, EDITOR_GROUPS,
    init_store, get_builds,
    get_build_offensive, get_build_defensive, get_build_weapon_meta,
    apply_card_effects, get_weights, render_sidebar,
)

st.set_page_config(page_title="Stat Optimization", layout="wide")
render_sidebar()

st.title("Stat Optimization")
st.caption(
    "Select an offensive build and one or more target builds to see effective stat multipliers "
    "and a ranked breakdown of stat investment priority."
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
        "Damage Type", ["Crit", "Penetration", "Hybrid"], horizontal=True, key="so_dmg_type",
        help=(
            "Crit or Penetration — uses a single ATK multiplier.  "
            "Hybrid — weights both; stat priorities reflect the blended damage."
        ),
    )
with col_atk:
    atk_type = st.radio(
        "Attack Type", ["Normal Attack", "Skill Attack"], horizontal=True, key="so_atk_type",
    )

_is_skill = atk_type == "Skill Attack"
_is_hybrid = dmg_type == "Hybrid"
col_size, col_elem, _ = st.columns([1, 2, 3])
with col_size:
    weapon_size_modifier = st.selectbox(
        "Weapon Size", options=SCENARIO_SELECT_FIELDS['weapon_size_modifier'],
        format_func=lambda x: f"{x}%",
        index=SCENARIO_SELECT_FIELDS['weapon_size_modifier'].index(100),
        key="so_weapon_size_modifier",
    )
with col_elem:
    elemental_counter = st.selectbox(
        "Elemental Counter", options=SCENARIO_SELECT_FIELDS['elemental_counter'],
        format_func=lambda x: f"{x}%",
        index=SCENARIO_SELECT_FIELDS['elemental_counter'].index(100),
        key="so_elemental_counter",
    )
col_pmatk, col_hits, col_hybrid = st.columns([1, 1, 2])
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
with col_hybrid:
    hybrid_crit_pct_raw = st.number_input(
        "% of DMG from Crit", min_value=0, max_value=100, value=50, step=1,
        key="so_hybrid_crit_pct", disabled=not _is_hybrid,
        help="Percentage of total damage dealt as crit hits. Pen% = 100 − this value.",
    )
    if _is_hybrid:
        pen_pct_display = 100 - hybrid_crit_pct_raw
        st.caption(f"Crit {hybrid_crit_pct_raw}%  ·  Pen {pen_pct_display}%")

hybrid_crit_pct = hybrid_crit_pct_raw / 100.0

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
    st.markdown("**Target Builds**")
    sel_def = st.multiselect("Select one or more target builds", options=build_names,
                              key="so_def_builds", label_visibility="collapsed")

if not sel_def:
    st.info("Select at least one target build above.")
    st.stop()

st.divider()

# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------
dmg_type_param = "hybrid" if dmg_type == "Hybrid" else ("pen" if dmg_type == "Penetration" else "crit")
attack_mult    = 16 if _is_skill else 8
_pmatk         = pmatk_pct if _is_skill else 100

base_off_raw = dict(get_build_offensive(sel_off))
base_off_raw['weapon_size_modifier'] = weapon_size_modifier
base_off_raw['elemental_counter']    = elemental_counter
wm = get_build_weapon_meta(sel_off)

def_raws = {name: get_build_defensive(name) for name in sel_def}
multi = len(sel_def) > 1

# Apply card effects per (off, def) pair, then scale patk
eff_off_raws: dict[str, dict] = {}
eff_def_raws: dict[str, dict] = {}
for def_name in sel_def:
    eff_off, eff_def = apply_card_effects(base_off_raw, def_raws[def_name], wm)
    eff_off = dict(eff_off)
    eff_off['patk'] = eff_off['patk'] * _pmatk / 100
    eff_off_raws[def_name] = eff_off
    eff_def_raws[def_name] = eff_def

# Weights per target (irrelevant dmg-type stat removed; hybrid keeps both)
all_weights: dict[str, dict[str, float]] = {}
_drake_active = wm.get("drake_card", False)
for def_name in sel_def:
    w = get_weights(mode, eff_off_raws[def_name], eff_def_raws[def_name],
                    dmg_type_param, attack_mult, hybrid_crit_pct)
    if dmg_type_param == "crit":
        w.pop('total_final_pen', None)
    elif dmg_type_param == "pen":
        w.pop('crit_dmg_bonus', None)
    # hybrid: keep both crit_dmg_bonus and total_final_pen
    # Drake Card (PVE): size stats are overridden by the card and cannot be invested in
    if _drake_active and mode == "PVE":
        w.pop('weapon_size_modifier', None)
        w.pop('size_enhance', None)
    all_weights[def_name] = {k: v for k, v in w.items() if k not in SCENARIO_SELECT_FIELDS}

# ---------------------------------------------------------------------------
# Effective multipliers per group
# ---------------------------------------------------------------------------
st.markdown("#### Effective Multipliers by Group")
if multi:
    st.caption(
        "Net multiplicative factor each stat group contributes. "
        "Avg shown; Min – Max range below (across selected target builds)."
    )
else:
    st.caption("Shows the net multiplicative factor each stat group contributes to the damage formula.")

eff_cols = st.columns(4)
col_idx = 0

# For hybrid, show both Crit and Pen groups (labelled with their split weights).
# For pure crit/pen, skip the inactive one.
if dmg_type_param == "crit":
    _skip_grps = {"Penetration"}
elif dmg_type_param == "pen":
    _skip_grps = {"Crit"}
else:
    _skip_grps = set()

for grp_label, icon, off_keys, def_keys, eff_pve, eff_pvp in EDITOR_GROUPS:
    if grp_label in _skip_grps:
        continue
    eff_fn = eff_pve if mode == "PVE" else eff_pvp
    if eff_fn is None:
        continue

    effs = []
    for def_name in sel_def:
        o_vals = {f: eff_off_raws[def_name].get(f, OFFENSIVE_FIELDS[f][1]) for f in off_keys}
        d_vals = {f: eff_def_raws[def_name].get(f, DEFENSIVE_FIELDS[f][1]) for f in def_keys}
        try:
            effs.append(eff_fn(o_vals, d_vals))
        except Exception:
            pass

    if not effs:
        continue

    avg_eff = sum(effs) / len(effs)
    color = "#2ecc71" if avg_eff >= 1.0 else "#e74c3c"

    # For hybrid, annotate the Crit/Pen group labels with their split weights
    display_label = grp_label
    if _is_hybrid and grp_label == "Crit":
        display_label = f"Crit ({hybrid_crit_pct_raw}%)"
    elif _is_hybrid and grp_label == "Penetration":
        display_label = f"Pen ({100 - hybrid_crit_pct_raw}%)"

    with eff_cols[col_idx % 4]:
        range_html = ""
        if multi:
            min_eff = min(effs)
            max_eff = max(effs)
            range_html = (
                f'<div style="font-size:11px; color:#888; margin-top:4px;">'
                f'↕ {min_eff:.3f}× – {max_eff:.3f}×</div>'
            )
        st.markdown(f"""
        <div style="background:rgba(255,255,255,0.05); border-radius:8px;
                    padding:12px 14px; margin-bottom:10px; text-align:center;">
            <div style="font-size:11px; color:#888; text-transform:uppercase;
                        letter-spacing:1px; margin-bottom:4px;">{icon} {display_label}</div>
            <div style="font-size:28px; font-weight:700; color:{color};">{avg_eff:.3f}×</div>
            {range_html}
        </div>
        """, unsafe_allow_html=True)
    col_idx += 1

st.divider()

# ---------------------------------------------------------------------------
# Stat priority
# ---------------------------------------------------------------------------
st.markdown("#### Stat Priority")
if multi:
    st.caption(
        "Ranked by average normalized priority across all target builds. "
        "Score is normalized so the best stat = 1.00. "
        "Equivalence shows how many points of each stat equal 1 point of the reference (★). "
        "Per-target scores are shown beneath each stat."
    )
else:
    st.caption(
        "Bars show relative priority vs the selected reference stat (★). "
        "Score is normalized so the best stat = 1.00. "
        "Equivalence shows how many points of each stat equal 1 point of the reference."
    )

labels_map = {f: label for f, (label, _) in OFFENSIVE_FIELDS.items()}

# Collect all fields with a positive weight in at least one target
all_fields: set[str] = set()
for w in all_weights.values():
    all_fields.update(k for k, v in w.items() if v > 0)

if not all_fields:
    st.warning("No positive-weight stats found for the current configuration.")
    st.stop()

# Normalise each target's weights independently (best stat per target = 1.0),
# then average those per-target scores → main bar value.
# Sub-bars use the same denominator as the main bars.
norm_by_target: dict[str, dict[str, float]] = {}
for def_name, w in all_weights.items():
    pos_vals = [v for v in w.values() if v > 0]
    max_w = max(pos_vals) if pos_vals else 1.0
    norm_by_target[def_name] = {f: w.get(f, 0.0) / max_w for f in all_fields}

avg_norm = {
    f: sum(norm_by_target[d].get(f, 0.0) for d in sel_def) / len(sel_def)
    for f in all_fields
}
avg_norm = {f: v for f, v in avg_norm.items() if v > 0}

if not avg_norm:
    st.warning("No positive-weight stats found for the current configuration.")
    st.stop()

best_stat = max(avg_norm, key=avg_norm.get)

st.markdown(f"""
<div style="background: rgba(46,204,113,0.1); border-left: 3px solid #2ecc71;
            border-radius: 0 6px 6px 0; padding: 8px 14px; margin-bottom: 12px;">
    <span style="color:#2ecc71; font-weight:700;">▲ Top priority: {labels_map[best_stat]}</span>
    <span style="color:#aaa; font-size:13px;"> — invest here for the greatest DPS gain per point.</span>
</div>
""", unsafe_allow_html=True)

ref_options = sorted(avg_norm.keys(), key=lambda k: labels_map[k])
current_ref = st.session_state.get("so_ref", best_stat)
if current_ref not in ref_options:
    current_ref = best_stat
reference = st.selectbox(
    "Reference stat for equivalence", options=ref_options,
    format_func=lambda k: labels_map[k],
    index=ref_options.index(current_ref),
    key="so_ref",
)

ref_avg      = avg_norm[reference]
sorted_items = sorted(avg_norm.items(), key=lambda x: x[1], reverse=True)
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

def _score_color(score: float) -> tuple[str, str]:
    """Interpolate bg color across blue→green→gold based on score in [0, 1]."""
    anchors = [(1.0, (255, 215, 0)), (0.5, (46, 204, 113)), (0.0, (93, 173, 226))]
    rgb = (93, 173, 226)
    for i in range(len(anchors) - 1):
        hi_v, hi_c = anchors[i]
        lo_v, lo_c = anchors[i + 1]
        if score >= lo_v:
            t = (score - lo_v) / (hi_v - lo_v) if hi_v != lo_v else 1.0
            rgb = tuple(int(lo_c[j] + t * (hi_c[j] - lo_c[j])) for j in range(3))
            break
    bg = f'#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}'
    fg = '#1a1a1a'
    return bg, fg


rows_html = ""
for rank, (field, avg_v) in enumerate(sorted_items):
    label  = labels_map[field]
    is_ref = field == reference
    norm   = avg_v
    equiv  = ref_avg / avg_v if avg_v > 0 else 0

    bg, fg = _score_color(norm)

    bar_w  = int(norm * 100)
    n_sty  = "font-weight:700;" if is_ref else ""
    star   = " ★" if is_ref else ""
    eq_str = "1.00" if is_ref else f"{equiv:.2f}"

    rows_html += f"""
    <div style="display:flex; align-items:center; gap:8px; margin-bottom:{'4px' if multi else '7px'};">
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

    if multi:
        for def_name in sel_def:
            t_norm  = norm_by_target[def_name].get(field, 0.0)
            t_bar_w = int(t_norm * 100)
            rows_html += f"""
    <div style="display:flex; align-items:center; gap:8px; margin-bottom:3px; padding-left:34px; opacity:0.65;">
        <div style="flex:2; font-size:11px; color:#aaa; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{def_name}</div>
        <div style="flex:3; background:rgba(255,255,255,0.05); border-radius:3px; height:7px; overflow:hidden;">
            <div style="width:{t_bar_w}%; height:100%; background:{bg}; border-radius:3px; opacity:0.55;"></div>
        </div>
        <div style="flex:1; text-align:right; font-family:monospace; font-size:11px; color:#888; padding-right:8px;">{t_norm:.2f}</div>
        <div style="flex:1;"></div>
    </div>
            """
        rows_html += '<div style="margin-bottom:10px;"></div>'

st.html(header_html + rows_html)