"""
Enchant Optimizer
-----------------
Finds the optimal weapon enchant combination to maximise average damage
across one or more target builds.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from collections import Counter
from itertools import combinations_with_replacement

import streamlit as st

from build_store import (
    OFFENSIVE_FIELDS,
    SELECT_FIELDS,
    init_store, get_builds,
    get_build_offensive, get_build_defensive, get_build_weapon_meta,
    calculate, render_sidebar,
)
from data.enchants_data import (
    get_enchant_awakening_info, get_weapon_enchant_options,
    ENCHANT_STAT_LABELS, QUALITY_OPTIONS,
)

st.set_page_config(page_title="Enchant Optimizer", layout="wide")
render_sidebar()

st.title("Enchant Optimizer")
st.caption(
    "Find the optimal weapon enchant combination to maximise damage output. "
    "Build stats should represent your character **without** weapon enchant contributions."
)

init_store()
builds    = get_builds()
build_names = list(builds.keys())

if not build_names:
    st.info("No builds saved yet. Create one in the **Build Editor** page.")
    st.stop()

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------
col_mode, col_dmg, col_atk = st.columns([1, 2, 2])
with col_mode:
    mode = st.radio("Mode", ["PVE", "PVP"], horizontal=True, key="eo_mode")
with col_dmg:
    dmg_type = st.radio(
        "Damage Type", ["Crit", "Penetration"], horizontal=True, key="eo_dmg_type",
    )
with col_atk:
    atk_type = st.radio(
        "Attack Type", ["Normal Attack", "Skill Attack"], horizontal=True, key="eo_atk_type",
    )

_is_skill = atk_type == "Skill Attack"
col_pmatk, col_hits, _ = st.columns([1, 1, 4])
with col_pmatk:
    pmatk_pct = st.number_input(
        "P/MATK% Modifier", min_value=0, max_value=99999, value=100, step=1,
        key="eo_pmatk_pct", disabled=not _is_skill,
    )
with col_hits:
    num_hits = st.number_input(
        "Number of Hits", min_value=1, max_value=99, value=1, step=1,
        key="eo_num_hits", disabled=not _is_skill,
    )

st.divider()

# ---------------------------------------------------------------------------
# Build selection
# ---------------------------------------------------------------------------
col_off, col_def = st.columns(2)
with col_off:
    st.markdown("**Offensive Build**")
    sel_off = st.selectbox("Offensive build", options=build_names,
                            key="eo_off_build", label_visibility="collapsed")
with col_def:
    st.markdown("**Target Builds**")
    sel_def = st.multiselect("Target builds", options=build_names,
                              key="eo_def_builds", label_visibility="collapsed")

if not sel_def:
    st.info("Select at least one target build.")
    st.stop()

st.divider()

# ---------------------------------------------------------------------------
# Weapon metadata (read from build)
# ---------------------------------------------------------------------------
wm          = get_build_weapon_meta(sel_off)
weapon_type = wm["weapon_type"]
awakening   = wm["enchant_awakening"]
awk_info    = get_enchant_awakening_info(awakening)
enchant_lvl = awk_info["enchant_lvl"]
modifier    = awk_info["modifier"]

col_wt, col_awk, col_qual = st.columns([2, 2, 2])
with col_wt:
    st.markdown(f"**Weapon Type:** {weapon_type.title()}")
with col_awk:
    st.markdown(f"**Enchant Awakening:** {awakening}  →  Level {enchant_lvl}  ·  ×{modifier:.1f}")
with col_qual:
    quality = st.selectbox(
        "Candidate Quality", QUALITY_OPTIONS,
        index=QUALITY_OPTIONS.index("Orange"), key="eo_quality",
    )

if awakening == 0:
    st.info("This build has no enchant awakening level set. Visit the Build Editor to configure it. Using enchant level 1 (no modifier).")

st.divider()

# ---------------------------------------------------------------------------
# Optimization
# ---------------------------------------------------------------------------
dmg_type_param = "pen" if dmg_type == "Penetration" else "crit"
attack_mult    = 16 if _is_skill else 8
_pmatk         = pmatk_pct if _is_skill else 100
_hits          = num_hits  if _is_skill else 1

off_raw_base = dict(get_build_offensive(sel_off))
off_raw_base["patk"] = off_raw_base["patk"] * _pmatk / 100
def_raws = {name: get_build_defensive(name) for name in sel_def}


def _score(off: dict) -> float:
    vals = [
        calculate(mode, off, def_raws[d], dmg_type_param, attack_mult) * _hits
        for d in sel_def
    ]
    return sum(vals) / len(vals)


def _per_target(off: dict) -> dict[str, float]:
    return {
        d: calculate(mode, off, def_raws[d], dmg_type_param, attack_mult) * _hits
        for d in sel_def
    }


def _apply_combo(base: dict, *combos) -> dict:
    result = dict(base)
    for combo in combos:
        for stat_en, field, eff_val in combo:
            result[field] = result.get(field, 0) + eff_val
    return result


def _combo_label(combo: tuple) -> str:
    counts = Counter((stat_en, eff_val) for stat_en, field, eff_val in combo)
    parts = []
    for (stat_en, eff_val), n in sorted(counts.items()):
        label = ENCHANT_STAT_LABELS.get(stat_en, stat_en)
        if n > 1:
            parts.append(f"{label} +{eff_val:g} ×{n}")
        else:
            parts.append(f"{label} +{eff_val:g}")
    return ",  ".join(parts) if parts else "—"


def _opts_to_tuples(opts: list[dict]) -> list[tuple]:
    return [(o["stat_en"], o["field"], o["effective_value"]) for o in opts]


def _run_optimize():
    main_opts = _opts_to_tuples(
        get_weapon_enchant_options(weapon_type, enchant_lvl, quality, modifier)
    )
    main_combos = list(combinations_with_replacement(main_opts, 3)) if main_opts else [()]

    if weapon_type == "one-handed":
        sub_opts   = _opts_to_tuples(
            get_weapon_enchant_options("sub", enchant_lvl, quality, modifier)
        )
        sub_combos = list(combinations_with_replacement(sub_opts, 3)) if sub_opts else [()]
    else:
        sub_combos = [()]

    results: list[tuple] = []   # (avg_score, per_target, main_combo, sub_combo)
    for mc in main_combos:
        for sc in sub_combos:
            off = _apply_combo(off_raw_base, mc, sc)
            avg = _score(off)
            pt  = _per_target(off)
            results.append((avg, pt, mc, sc))

    results.sort(key=lambda x: x[0], reverse=True)
    return results[:5]


# Baseline (no enchants added)
baseline_score = _score(off_raw_base)
baseline_pt    = _per_target(off_raw_base)

if st.button("⚡ Optimize", type="primary", use_container_width=False):
    with st.spinner("Evaluating enchant combinations…"):
        top5 = _run_optimize()
    st.session_state["eo_results"] = top5
    st.rerun()

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
top5 = st.session_state.get("eo_results")
if not top5:
    st.stop()

st.divider()
st.markdown("#### Top 5 Enchant Combinations")
multi = len(sel_def) > 1

all_scores = [r[0] for r in top5] + [baseline_score]
max_score  = max(all_scores) if all_scores else 1.0


def _score_color(norm: float) -> tuple[str, str]:
    anchors = [(1.0, (255, 215, 0)), (0.5, (46, 204, 113)), (0.0, (93, 173, 226))]
    rgb = (93, 173, 226)
    for i in range(len(anchors) - 1):
        hi_v, hi_c = anchors[i]
        lo_v, lo_c = anchors[i + 1]
        if norm >= lo_v:
            t = (norm - lo_v) / (hi_v - lo_v) if hi_v != lo_v else 1.0
            rgb = tuple(int(lo_c[j] + t * (hi_c[j] - lo_c[j])) for j in range(3))
            break
    bg = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
    fg = "#1a1a1a" if norm > 0.75 else "#ffffff"
    return bg, fg


header_html = """
<div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;
            padding-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.15);
            color:#888; font-size:11px; text-transform:uppercase; letter-spacing:1px;">
    <div style="width:26px; flex-shrink:0;"></div>
    <div style="flex:3;">Enchant Combination</div>
    <div style="flex:3;">Damage Output</div>
    <div style="flex:1; text-align:right;">Avg Multiplier</div>
</div>
"""

rows_html = ""

def _result_row(rank_label: str, bg: str, fg: str, combo_text: str,
                avg: float, per_target: dict) -> str:
    norm  = avg / max_score if max_score else 0
    bar_w = int(norm * 100)
    html  = f"""
<div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
    <div style="background:{bg}; color:{fg}; border-radius:50%;
                width:26px; height:26px; display:flex; align-items:center;
                justify-content:center; font-size:11px; font-weight:700; flex-shrink:0;">
        {rank_label}
    </div>
    <div style="flex:3; font-size:12px; font-weight:600;">{combo_text}</div>
    <div style="flex:3; background:rgba(255,255,255,0.08); border-radius:4px; height:14px; overflow:hidden;">
        <div style="width:{bar_w}%; height:100%; background:{bg}; border-radius:4px;"></div>
    </div>
    <div style="flex:1; text-align:right; font-family:monospace; font-size:13px; color:#ccc;">
        {avg:,.2f}
    </div>
</div>
"""
    if multi:
        for def_name, val in per_target.items():
            sub_norm  = val / max_score if max_score else 0
            sub_bar_w = int(sub_norm * 100)
            html += f"""
<div style="display:flex; align-items:center; gap:8px; margin-bottom:3px;
            padding-left:34px; opacity:0.65;">
    <div style="flex:3; font-size:11px; color:#aaa; white-space:nowrap;
                overflow:hidden; text-overflow:ellipsis;">{def_name}</div>
    <div style="flex:3; background:rgba(255,255,255,0.05); border-radius:3px;
                height:7px; overflow:hidden;">
        <div style="width:{sub_bar_w}%; height:100%; background:{bg};
                    border-radius:3px; opacity:0.55;"></div>
    </div>
    <div style="flex:1; text-align:right; font-family:monospace; font-size:11px;
                color:#888;">{val:,.2f}</div>
</div>"""
    html += '<div style="margin-bottom:10px;"></div>'
    return html


for rank, (r_avg, r_per_target, r_mc, r_sc) in enumerate(top5):
    r_norm = r_avg / max_score if max_score else 0
    r_bg, r_fg = _score_color(r_norm)

    main_label = _combo_label(r_mc)
    sub_label  = _combo_label(r_sc) if r_sc else ""
    if sub_label and sub_label != "—":
        r_combo_text = f"Main: {main_label}  |  Sub: {sub_label}"
    else:
        r_combo_text = main_label

    rows_html += _result_row(str(rank + 1), r_bg, r_fg, r_combo_text, r_avg, r_per_target)

# Baseline row
b_norm = baseline_score / max_score if max_score else 0
b_bg, b_fg = "#666666", "#ffffff"
rows_html += _result_row("—", b_bg, b_fg, "Baseline (no enchants)", baseline_score, baseline_pt)

st.html(header_html + rows_html)
