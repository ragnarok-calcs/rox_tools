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
    PCT_FIELDS, SELECT_FIELDS, EDITOR_GROUPS,
    init_store, get_builds,
    get_build_offensive, get_build_defensive,
    get_weights, render_sidebar,
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
dmg_type_param = "pen" if dmg_type == "Penetration" else "crit"
attack_mult    = 16 if _is_skill else 8
_pmatk         = pmatk_pct if _is_skill else 100

off_raw = dict(get_build_offensive(sel_off))
off_raw['patk'] = off_raw['patk'] * _pmatk / 100

def_raws = {name: get_build_defensive(name) for name in sel_def}
multi = len(sel_def) > 1

# Weights per target (inactive dmg-type stat and select fields removed)
all_weights: dict[str, dict[str, float]] = {}
for def_name in sel_def:
    w = get_weights(mode, off_raw, def_raws[def_name], dmg_type_param, attack_mult)
    if dmg_type_param == "crit":
        w.pop('total_final_pen', None)
    else:
        w.pop('crit_dmg_bonus', None)
    all_weights[def_name] = {k: v for k, v in w.items() if k not in SELECT_FIELDS}

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

_skip_grp = "Penetration" if dmg_type_param == "crit" else "Crit"
for grp_label, icon, off_keys, def_keys, eff_pve, eff_pvp in EDITOR_GROUPS:
    if grp_label == _skip_grp:
        continue
    eff_fn = eff_pve if mode == "PVE" else eff_pvp
    if eff_fn is None:
        continue

    o_vals = {f: off_raw.get(f, OFFENSIVE_FIELDS[f][1]) for f in off_keys}

    effs = []
    for def_name in sel_def:
        d_vals = {f: def_raws[def_name].get(f, DEFENSIVE_FIELDS[f][1]) for f in def_keys}
        try:
            effs.append(eff_fn(o_vals, d_vals))
        except Exception:
            pass

    if not effs:
        continue

    avg_eff = sum(effs) / len(effs)
    color = "#2ecc71" if avg_eff >= 1.0 else "#e74c3c"

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
                        letter-spacing:1px; margin-bottom:4px;">{icon} {grp_label}</div>
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