"""
DPS Simulator
-------------
Select a class skill set and one or more offensive builds, then run a
Monte Carlo priority-queue simulation to estimate DPS against a target build.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st

from build_store import (
    init_store, get_builds,
    get_build_offensive, get_build_defensive, get_build_weapon_meta,
    render_sidebar,
)
from dps_simulator.engine import (
    discover_skill_sets, load_skill_set,
    SkillDef, BuffDef, SimConfig, SimResult, run_simulation,
)

st.set_page_config(page_title="DPS Simulator", layout="wide")
render_sidebar()

st.title("DPS Simulator")
st.caption(
    "Simulate DPS for a class rotation using a priority-based skill queue. "
    "Damage is calculated from your saved builds via the same formula as the Damage Calculator."
)

init_store()
builds     = get_builds()
build_names = list(builds.keys())

if not build_names:
    st.info("No builds saved yet. Create one in the **Build Editor** page.")
    st.stop()

# ---------------------------------------------------------------------------
# Rotation source selection
# ---------------------------------------------------------------------------
if "rotations" not in st.session_state:
    st.session_state["rotations"] = {}

col_src, _ = st.columns([2, 5])
with col_src:
    rotation_source = st.radio(
        "Rotation Source",
        ["DEV Skill Set", "User Rotation"],
        horizontal=True,
        key="dps_rotation_source",
    )

skill_sets = discover_skill_sets()
user_rotations = st.session_state["rotations"]

if rotation_source == "DEV Skill Set":
    if not skill_sets:
        st.error(
            "No skill set files found in `data/skill_sets/`. "
            "Add a JSON file to define a class rotation."
        )
        st.stop()
    col_class, _ = st.columns([2, 5])
    with col_class:
        selected_class = st.selectbox("Class / Skill Set", list(skill_sets.keys()), key="dps_class_sel")
    try:
        skill_defs = load_skill_set(skill_sets[selected_class])
    except Exception as e:
        st.error(f"Failed to load skill set '{selected_class}': {e}")
        st.stop()
else:
    if not user_rotations:
        st.info("No rotations saved yet. Create one in the **Rotation Builder** page.")
        st.stop()
    col_rot, _ = st.columns([2, 5])
    with col_rot:
        selected_rotation = st.selectbox("User Rotation", list(user_rotations.keys()), key="dps_user_rot_sel")
    stored = user_rotations[selected_rotation]
    try:
        def _parse_buff(s):
            bd = s.get("buff")
            if not bd or not bd.get("stat_field"):
                return None
            return BuffDef(
                stat_field=bd["stat_field"],
                flat_value=float(bd.get("flat_value", 0.0)),
                duration=float(bd.get("duration", 0.0)),
                stackable=bool(bd.get("stackable", False)),
            )

        skill_defs = [
            SkillDef(
                id=s["id"],
                name=s["name"],
                pmatk_pct=float(s.get("pmatk_pct", 100)),
                num_hits=int(s.get("num_hits", 1)),
                dmg_type=s.get("dmg_type", "crit"),
                attack_mult=int(s.get("attack_mult", 16)),
                FCD=float(s.get("FCD", 0.0)),
                VCD_base=float(s.get("VCD_base", 0.0)),
                animation=float(s.get("animation", 0.6)),
                crit_tick=bool(s.get("crit_tick", False)),
                proc_id=s.get("proc_id"),
                proc_chance=float(s.get("proc_chance", 0.0)),
                proc_advances_clock=bool(s.get("proc_advances_clock", False)),
                priority=int(s.get("priority", 99)),
                proc_only=bool(s.get("proc_only", False)),
                is_normal_attack=bool(s.get("is_normal_attack", False)),
                buff=_parse_buff(s),
            )
            for s in sorted(stored, key=lambda x: x.get("priority", 99))
        ]
    except Exception as e:
        st.error(f"Failed to load rotation '{selected_rotation}': {e}")
        st.stop()

st.divider()

# ---------------------------------------------------------------------------
# Simulation parameters
# ---------------------------------------------------------------------------
col_mode, col_dmg, col_time, col_runs = st.columns([1, 2, 1, 1])
with col_mode:
    mode = st.radio("Mode", ["PVE", "PVP"], horizontal=True, key="dps_mode")
with col_dmg:
    dmg_override_label = st.radio(
        "Damage Type",
        ["Per-skill default", "Force Crit", "Force Pen"],
        horizontal=True, key="dps_dmg_type",
        help="Override every skill's damage type, or use the type set in the skill definition.",
    )
with col_time:
    sim_duration = st.number_input(
        "Duration (s)", min_value=30, max_value=3600, value=300, step=30,
        key="dps_sim_time",
    )
with col_runs:
    num_runs = st.number_input(
        "Runs", min_value=1, max_value=1000, value=50, step=10,
        key="dps_num_runs",
        help="Monte Carlo runs averaged together. 50+ gives stable results.",
    )

dmg_type_override = (
    None        if dmg_override_label == "Per-skill default" else
    "crit"      if dmg_override_label == "Force Crit"        else
    "pen"
)

# ---------------------------------------------------------------------------
# Build selection
# ---------------------------------------------------------------------------
col_off, col_def = st.columns(2)
with col_off:
    st.markdown("**Offensive Builds**")
    sel_off = st.multiselect(
        "Select one or more offensive builds", options=build_names,
        key="dps_off_builds", label_visibility="collapsed",
    )
with col_def:
    st.markdown("**Target Build**")
    sel_def = st.selectbox(
        "Select target build", options=build_names,
        key="dps_def_build", label_visibility="collapsed",
    )

if not sel_off or not sel_def:
    st.info("Select at least one offensive build and a target build above.")
    st.stop()

# ---------------------------------------------------------------------------
# Skill rotation preview
# ---------------------------------------------------------------------------
with st.expander("📋 Skill Rotation", expanded=False):
    skill_id_map = {d.id: d for d in skill_defs}
    queue_skills = [d for d in skill_defs if not d.proc_only]
    proc_skills  = [d for d in skill_defs if d.proc_only]

    st.markdown("**Priority Queue** — highest-priority skill with CD = 0 fires each tick")
    for i, d in enumerate(queue_skills):
        tags = []
        if d.is_normal_attack:
            tags.append("★ Normal Attack")
        if d.crit_tick:
            tags.append("CT tick")
        if d.proc_id and d.proc_id in skill_id_map:
            proc_d   = skill_id_map[d.proc_id]
            clk_note = "advances clock" if proc_d.proc_advances_clock else "free dmg"
            tags.append(f"{d.proc_chance * 100:.0f}% → {proc_d.name} ({clk_note})")
        if d.buff is not None:
            stack_note = "stackable" if d.buff.stackable else "refresh"
            tags.append(f"BUFF +{d.buff.flat_value:.0f} {d.buff.stat_field}  {d.buff.duration:.0f}s  [{stack_note}]")
        tag_str = "  ·  " + "  ·  ".join(tags) if tags else ""
        st.caption(
            f"**{i + 1}. {d.name}**  —  "
            f"FCD {d.FCD}s  VCD {d.VCD_base}s  anim {d.animation}s  "
            f"{d.pmatk_pct:.0f}% × {d.num_hits} hit"
            f"{tag_str}"
        )

    if proc_skills:
        st.markdown("**Proc-only Skills**")
        for d in proc_skills:
            clk_note = "advances clock" if d.proc_advances_clock else "free dmg"
            buff_note = ""
            if d.buff is not None:
                stack_note = "stackable" if d.buff.stackable else "refresh"
                buff_note = f"  ·  BUFF +{d.buff.flat_value:.0f} {d.buff.stat_field}  {d.buff.duration:.0f}s  [{stack_note}]"
            st.caption(
                f"• **{d.name}**  —  "
                f"{d.pmatk_pct:.0f}% × {d.num_hits} hit  "
                f"anim {d.animation}s  ({clk_note})"
                f"{buff_note}"
            )

st.divider()

# ---------------------------------------------------------------------------
# Run simulation
# ---------------------------------------------------------------------------
if st.button("▶ Run Simulation", type="primary"):
    def_raw = get_build_defensive(sel_def)
    config  = SimConfig(
        mode=mode,
        dmg_type_override=dmg_type_override,
        sim_duration=float(sim_duration),
        num_runs=int(num_runs),
    )

    sim_results: dict[str, SimResult] = {}
    prog = st.progress(0, text="Simulating…")
    for idx, off_name in enumerate(sel_off):
        off_raw = dict(get_build_offensive(off_name))
        wm      = get_build_weapon_meta(off_name)
        sim_results[off_name] = run_simulation(skill_defs, off_raw, def_raw, wm, config)
        prog.progress((idx + 1) / len(sel_off), text=f"Completed: {off_name}")
    prog.empty()

    st.session_state["dps_results"]   = sim_results
    st.session_state["dps_off_names"] = sel_off
    st.session_state["dps_def_name"]  = sel_def

if "dps_results" not in st.session_state:
    st.stop()

sim_results = st.session_state["dps_results"]
off_names   = st.session_state["dps_off_names"]
def_name    = st.session_state["dps_def_name"]


# ---------------------------------------------------------------------------
# Helper: per-skill breakdown table
# ---------------------------------------------------------------------------
def _render_skill_table(res: SimResult):
    if not res.skill_results:
        st.caption("No skill data.")
        return

    max_dps = max((r.dps_contribution for r in res.skill_results), default=1.0) or 1.0

    header_html = """
    <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;
                padding-bottom:5px; border-bottom:1px solid rgba(255,255,255,0.15);
                color:#888; font-size:11px; text-transform:uppercase; letter-spacing:1px;">
        <div style="flex:2;">Skill</div>
        <div style="flex:3;">DPS Share</div>
        <div style="flex:1; text-align:right;">% DPS</div>
        <div style="flex:1; text-align:right;">Casts</div>
        <div style="flex:1; text-align:right;">Casts/min</div>
    </div>"""

    rows_html = ""
    for r in res.skill_results:
        bar_w = int(r.dps_contribution / max_dps * 100)
        rows_html += f"""
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:7px;">
            <div style="flex:2; font-size:13px;">{r.skill_name}</div>
            <div style="flex:3; background:rgba(255,255,255,0.08); border-radius:4px;
                        height:14px; overflow:hidden;">
                <div style="width:{bar_w}%; height:100%; background:#e74c3c;
                            border-radius:4px;"></div>
            </div>
            <div style="flex:1; text-align:right; font-family:monospace;
                        font-size:13px; color:#ccc;">{r.pct_of_total_dps:.1f}%</div>
            <div style="flex:1; text-align:right; font-family:monospace;
                        font-size:12px; color:#aaa;">{r.cast_count:,}</div>
            <div style="flex:1; text-align:right; font-family:monospace;
                        font-size:12px; color:#aaa;">{r.casts_per_min:.1f}</div>
        </div>"""

    st.html(header_html + rows_html)
    st.caption(
        f"Total DPS: **{res.total_dps:,.0f}**  ·  "
        f"avg over {res.run_count} runs  ·  {res.sim_duration:.0f}s simulated"
    )


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
if len(off_names) == 1:
    off_name = off_names[0]
    res      = sim_results[off_name]

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(231,76,60,0.15) 0%, rgba(26,26,46,0.6) 100%);
                border: 1px solid rgba(231,76,60,0.5); border-radius: 12px;
                padding: 20px 32px; text-align: center; margin: 16px 0;">
        <div style="font-size:13px; color:#aaa; text-transform:uppercase;
                    letter-spacing:2px; margin-bottom:8px;">
            {off_name}  ·  {def_name}
        </div>
        <div style="font-size:52px; font-weight:800; color:#e74c3c; line-height:1.1;">
            {res.total_dps:,.0f}
        </div>
        <div style="font-size:16px; color:#888; margin-top:4px;">DPS</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### Skill Breakdown")
    _render_skill_table(res)

else:
    sorted_names = sorted(off_names, key=lambda n: sim_results[n].total_dps, reverse=True)
    max_dps      = max(sim_results[n].total_dps for n in sorted_names) or 1.0

    bars_html = ""
    for off_name in sorted_names:
        dps   = sim_results[off_name].total_dps
        bar_w = int(dps / max_dps * 100)
        bars_html += f"""
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px;">
            <div style="flex:3; font-size:13px; color:#eee;">{off_name}</div>
            <div style="flex:5; background:rgba(255,255,255,0.08); border-radius:4px;
                        height:18px; overflow:hidden;">
                <div style="width:{bar_w}%; height:100%; background:#e74c3c;
                            border-radius:4px;"></div>
            </div>
            <div style="flex:1; text-align:right; font-family:monospace; font-size:14px;
                        color:#e74c3c; font-weight:700;">{dps:,.0f}</div>
            <div style="flex:0.5; font-size:11px; color:#888;">dps</div>
        </div>"""

    st.html(bars_html)
    st.divider()

    for off_name in sorted_names:
        res = sim_results[off_name]
        with st.expander(f"**{off_name}** — {res.total_dps:,.0f} DPS", expanded=False):
            _render_skill_table(res)
