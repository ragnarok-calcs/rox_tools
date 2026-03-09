import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
import streamlit as st
import plotly.graph_objects as go
from multiplier_stats import (
    PVEPlayerStats, PVETargetStats, pve_calculate_multiplier, pve_modifier_weights,
    PVPPlayerStats, PVPTargetStats, pvp_calculate_multiplier, pvp_modifier_weights,
    pen_multiplier,
)

st.set_page_config(page_title="DMG Multiplier", layout="wide")
st.title("DMG Multiplier")
st.caption(
    "Enter your current stats and target stats to see the overall damage multiplier "
    "and a ranked breakdown of which stats give the greatest DPS return per point invested."
)

# ---------------------------------------------------------------------------
# Field definitions: {field: (label, default)}
# ---------------------------------------------------------------------------
_PVE_PLAYER_FIELDS = {
    'patk':                 ('P.ATK',                  1000),
    'crit_dmg_bonus':       ('Crit DMG Bonus %',        200),
    'pdmg_bonus':           ('P.DMG Bonus',             0),
    'pdmg_bonus_pct':       ('P.DMG Bonus%',            0),
    'final_pdmg_bonus':     ('Final P.DMG Bonus %',     0),
    'elemental_counter':    ('Elemental Counter %',      100),
    'element_enhance':      ('Element Enhance %',        0),
    'bonus_dmg_element':    ('Bonus DMG to Element %',   0),
    'bonus_dmg_race':       ('Bonus DMG to Race %',      0),
    'final_dmg_bonus':      ('Final DMG Bonus %',        0),
    'weapon_size_modifier': ('Weapon Size Modifier %',   100),
    'size_enhance':         ('Bonus DMG to Size %',      0),
    'total_final_pen':      ('Total Final PEN %',        0),
}
_PVE_TARGET_FIELDS = {
    'crit_dmg_reduc':   ('Crit DMG Reduction %',     0),
    'pdmg_reduc':       ('P.DMG Reduction',           0),
    'final_pdmg_reduc': ('Final P.DMG Reduction %',   0),
    'final_dmg_reduc':  ('Final DMG Reduction %',     0),
    'total_final_def':  ('Total Final DEF %',          0),
}
_PVP_PLAYER_FIELDS = {
    'patk':                 ('P.ATK',                  1000),
    'crit_dmg_bonus':       ('Crit DMG Bonus %',        200),
    'pdmg_bonus':           ('P.DMG Bonus',             0),
    'pdmg_bonus_pct':       ('P.DMG Bonus%',            0),
    'final_pdmg_bonus':     ('Final P.DMG Bonus %',     0),
    'weapon_size_modifier': ('Weapon Size Modifier %',   100),
    'size_enhance':         ('Bonus DMG to Size %',      0),
    'bonus_dmg_race':       ('Bonus DMG to Race %',      0),
    'elemental_counter':    ('Elemental Counter %',      100),
    'element_enhance':      ('Element Enhance %',        0),
    'final_dmg_bonus':      ('Final DMG Bonus %',        0),
    'pvp_final_pdmg_bonus': ('PVP Final P.DMG Bonus %',  0),
    'pvp_pdmg_bonus':       ('PVP P.DMG Bonus',         0),
    'total_final_pen':      ('Total Final PEN %',        0),
}
_PVP_TARGET_FIELDS = {
    'crit_dmg_reduc':       ('Crit DMG Reduction %',        0),
    'pdmg_reduc':           ('P.DMG Reduction',             0.0),
    'final_pdmg_reduc':     ('Final P.DMG Reduction %',     0),
    'element_resist':       ('Element Resist %',             0),
    'size_reduc':           ('Size Reduction %',             0),
    'race_reduc':           ('Race Reduction %',             0),
    'final_dmg_reduc':      ('Final DMG Reduction %',        0),
    'pvp_pdmg_reduc':       ('PVP P.DMG Reduction',          0),
    'pvp_final_pdmg_reduc': ('PVP Final P.DMG Reduction %',  0),
    'total_final_def':      ('Total Final DEF %',            0),
}

_ALL_FIELDS = {
    'PVE': (_PVE_PLAYER_FIELDS, _PVE_TARGET_FIELDS),
    'PVP': (_PVP_PLAYER_FIELDS, _PVP_TARGET_FIELDS),
}

# Fields whose UI values are integer percentages (e.g. 20 → 0.20 in the formula).
_PCT_FIELDS = {
    'crit_dmg_bonus', 'final_pdmg_bonus', 'weapon_size_modifier', 'size_enhance',
    'bonus_dmg_race', 'elemental_counter', 'element_enhance', 'bonus_dmg_element',
    'final_dmg_bonus', 'pvp_final_pdmg_bonus',
    'total_final_pen',
    # Target reductions / pen
    'crit_dmg_reduc', 'final_pdmg_reduc', 'element_resist', 'size_reduc',
    'race_reduc', 'final_dmg_reduc', 'pvp_final_pdmg_reduc',
    'total_final_def',
}

# Flat stat fields entered as integers (not percentage, not float).
_INT_FIELDS = {'patk', 'pdmg_bonus', 'pdmg_bonus_pct', 'pdmg_reduc', 'pvp_pdmg_bonus', 'pvp_pdmg_reduc'}

# Fields rendered as selectboxes: {field: [option_ints]}
_SELECT_FIELDS = {
    'weapon_size_modifier': [75, 100],
    'elemental_counter':    [0, 25, 50, 70, 75, 90, 100, 125, 150, 175],
}

# Icons for stat group expander headers
_GROUP_ICONS = {
    'Base Attack':  '⚔️',
    'Crit':         '💥',
    'Penetration':  '🔱',
    'Final P.DMG':  '🎯',
    'Size':         '📏',
    'Element':      '🌀',
    'Race':         '👥',
    'Final DMG':    '🔥',
    'PVP DMG':      '⚡',
}


def _pen_effective_fn(p_vals: dict, t_vals: dict) -> float:
    """Compute the penetration ATK multiplier from raw UI values (integer %)."""
    pen_diff = (p_vals.get('total_final_pen', 0) - t_vals.get('total_final_def', 0)) / 100.0
    return pen_multiplier(pen_diff)


_PEN_GROUP = (
    'Penetration',
    ['total_final_pen'],
    ['total_final_def'],
    _pen_effective_fn,
)


def _get_groups(mode: str, dmg_type: str) -> list:
    """Return the stat input groups for the given mode and damage type."""
    base = _PVE_GROUPS if mode == "PVE" else _PVP_GROUPS
    if dmg_type == "Crit":
        return base
    # Swap the "Crit" group for the "Penetration" group
    return [_PEN_GROUP if g[0] == "Crit" else g for g in base]


# Grouped layout: list of (header, [player_fields], [target_fields])
_PVE_GROUPS = [
    ('Base Attack', ['patk', 'pdmg_bonus', 'pdmg_bonus_pct'],                      ['pdmg_reduc'],  None),
    ('Crit',        ['crit_dmg_bonus'],                                             ['crit_dmg_reduc'],
        lambda p, t: p['crit_dmg_bonus'] / 100 - t['crit_dmg_reduc'] / 100),
    ('Final P.DMG', ['final_pdmg_bonus'],                                           ['final_pdmg_reduc'],
        lambda p, t: max(1 + (p['final_pdmg_bonus'] - t['final_pdmg_reduc']) / 100, 0.2)),
    ('Size',        ['weapon_size_modifier', 'size_enhance'],                       [],
        lambda p, t: max((p['weapon_size_modifier'] + p['size_enhance']) / 100, 0.2)),
    ('Element',     ['elemental_counter', 'element_enhance', 'bonus_dmg_element'],  [],
        lambda p, t: max((p['elemental_counter'] + p['element_enhance']) / 100, 0.2) * (1 + p['bonus_dmg_element'] / 100)),
    ('Race',        ['bonus_dmg_race'],                                             [],
        lambda p, t: max(1 + p['bonus_dmg_race'] / 100, 0.2)),
    ('Final DMG',   ['final_dmg_bonus'],                                            ['final_dmg_reduc'],
        lambda p, t: max(1 + (p['final_dmg_bonus'] - t['final_dmg_reduc']) / 100, 0.2)),
]
_PVP_GROUPS = [
    ('Base Attack', ['patk', 'pdmg_bonus', 'pdmg_bonus_pct'],                      ['pdmg_reduc'],  None),
    ('Crit',        ['crit_dmg_bonus'],                                             ['crit_dmg_reduc'],
        lambda p, t: p['crit_dmg_bonus'] / 100 - t['crit_dmg_reduc'] / 100),
    ('Final P.DMG', ['final_pdmg_bonus'],                                           ['final_pdmg_reduc'],
        lambda p, t: max(1 + (p['final_pdmg_bonus'] - t['final_pdmg_reduc']) / 100, 0.2)),
    ('Size',        ['weapon_size_modifier', 'size_enhance'],                       ['size_reduc'],
        lambda p, t: max((p['weapon_size_modifier'] + p['size_enhance'] - t['size_reduc']) / 100, 0.2)),
    ('Element',     ['elemental_counter', 'element_enhance'],                       ['element_resist'],
        lambda p, t: max((p['elemental_counter'] + p['element_enhance'] - t['element_resist']) / 100, 0.2)),
    ('Race',        ['bonus_dmg_race'],                                             ['race_reduc'],
        lambda p, t: max(1 + (p['bonus_dmg_race'] - t['race_reduc']) / 100, 0.2)),
    ('Final DMG',   ['final_dmg_bonus'],                                            ['final_dmg_reduc'],
        lambda p, t: max(1 + (p['final_dmg_bonus'] - t['final_dmg_reduc']) / 100, 0.2)),
    ('PVP DMG',     ['pvp_pdmg_bonus', 'pvp_final_pdmg_bonus'],                    ['pvp_pdmg_reduc', 'pvp_final_pdmg_reduc'],
        lambda p, t: max(1 + (p['pvp_final_pdmg_bonus'] - t['pvp_final_pdmg_reduc']) / 100, 0.2)),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _field_key(prefix: str, field: str) -> str:
    return f"{prefix}_{field}"


def _render_input(field: str, label: str, default, key: str, on_change=None):
    kwargs = {"on_change": on_change} if on_change else {}
    if field in _SELECT_FIELDS:
        options = _SELECT_FIELDS[field]
        return st.selectbox(
            label, options=options, index=options.index(int(default)),
            format_func=lambda x: f"{x}%", key=key, **kwargs,
        )
    elif field in _PCT_FIELDS or field in _INT_FIELDS:
        return st.number_input(label, value=int(default), min_value=0, step=1, key=key, **kwargs)
    else:
        return st.number_input(label, value=default, min_value=0.0, key=key, **kwargs)


def _read_from_session(fields: dict, key_prefix: str) -> dict:
    return {
        field: st.session_state.get(_field_key(key_prefix, field), default)
        for field, (_, default) in fields.items()
    }


def _apply_player_build(build: dict):
    mode = build["mode"]
    p_fields, _ = _ALL_FIELDS[mode]
    st.session_state["dm_mode"] = mode
    for field, value in build.get("stats", {}).items():
        if field in p_fields:
            v = int(value) if field in _SELECT_FIELDS else float(value)
            st.session_state[_field_key(f"dm_p_{mode}", field)] = v


def _apply_target_build(build: dict):
    mode = build["mode"]
    _, t_fields = _ALL_FIELDS[mode]
    for field, value in build.get("stats", {}).items():
        if field in t_fields:
            st.session_state[_field_key(f"dm_t_{mode}", field)] = float(value)


def _pct_to_decimal(vals: dict) -> dict:
    """Convert integer-percentage fields to their decimal equivalents for formula use."""
    return {k: v / 100.0 if k in _PCT_FIELDS else v for k, v in vals.items()}


def _read_from_build(build_stats: dict, fields: dict) -> dict:
    """Read stat values from a saved build dict, falling back to field defaults."""
    return {f: build_stats.get(f, default) for f, (_, default) in fields.items()}


def _calculate(mode: str, p_dec: dict, t_dec: dict, dmg_type: str) -> float:
    """Dispatch to the correct PVE/PVP multiplier calculation."""
    if mode == "PVE":
        return pve_calculate_multiplier(PVEPlayerStats(**p_dec), PVETargetStats(**t_dec), dmg_type)
    return pvp_calculate_multiplier(PVPPlayerStats(**p_dec), PVPTargetStats(**t_dec), dmg_type)


def _weights(mode: str, p_dec: dict, t_dec: dict, dmg_type: str) -> dict[str, float]:
    """Dispatch to the correct PVE/PVP modifier weights calculation."""
    if mode == "PVE":
        return pve_modifier_weights(PVEPlayerStats(**p_dec), PVETargetStats(**t_dec), dmg_type)
    return pvp_modifier_weights(PVPPlayerStats(**p_dec), PVPTargetStats(**t_dec), dmg_type)


def _make_bar_chart(
    values: list, labels: list, colors: list,
    x_title: str = "", hover_tpl: str = "", right_margin: int = 80,
) -> go.Figure:
    """Create a horizontal bar chart with shared layout conventions."""
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation='h',
        marker=dict(color=colors, line=dict(width=0)),
        text=[f"{v:,.2f}" for v in values],
        textposition='outside',
        textfont=dict(size=11),
        hovertemplate=hover_tpl,
    ))
    fig.update_layout(
        xaxis=dict(title=x_title, showgrid=False, zeroline=False, showline=False),
        yaxis=dict(autorange='reversed', showgrid=False, tickfont=dict(size=12)),
        margin=dict(l=0, r=right_margin, t=10, b=40),
        height=60 + 40 * len(values),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
    )
    return fig


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    max_w = max(abs(v) for v in weights.values())
    if max_w == 0:
        return {k: 0.0 for k in weights}
    return {k: v / max_w for k, v in weights.items()}


def _gradient_colors(values: list) -> list:
    """Interpolate colors gold → green → steel-blue based on normalized value."""
    anchors = [
        (1.0, (255, 215,   0)),  # gold
        (0.5, ( 46, 204, 113)),  # green
        (0.0, ( 93, 173, 226)),  # steel blue
    ]
    colors = []
    for v in values:
        v = max(0.0, min(1.0, v))
        color = (93, 173, 226)
        for i in range(len(anchors) - 1):
            hi_v, hi_c = anchors[i]
            lo_v, lo_c = anchors[i + 1]
            if v >= lo_v:
                t = (v - lo_v) / (hi_v - lo_v) if hi_v != lo_v else 1.0
                r = int(lo_c[0] + t * (hi_c[0] - lo_c[0]))
                g = int(lo_c[1] + t * (hi_c[1] - lo_c[1]))
                b = int(lo_c[2] + t * (hi_c[2] - lo_c[2]))
                color = (r, g, b)
                break
        colors.append(f'#{color[0]:02x}{color[1]:02x}{color[2]:02x}')
    return colors


def _rank_color(rank: int) -> tuple:
    """Return (bg_color, text_color) for a rank badge."""
    if rank == 0:
        return ('#FFD700', '#1a1a1a')   # gold
    elif rank <= 2:
        return ('#2ecc71', '#ffffff')   # green
    else:
        return ('#5dade2', '#ffffff')   # steel blue


def _render_combined(weights: dict[str, float], labels: dict[str, str], reference: str):
    """Priority bars normalized to the selected reference, with equivalence column."""
    ref_w = weights[reference]
    max_w = max(weights.values())
    sorted_items = sorted(
        [(k, v) for k, v in weights.items() if v > 0],
        key=lambda x: x[1], reverse=True,
    )

    ref_label = labels[reference]
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
        label = labels[field]
        is_ref = field == reference
        norm_score = w / max_w
        equiv = ref_w / w
        bg_color, txt_color = _rank_color(rank)
        bar_width = int(norm_score * 100)
        name_style = "font-weight:700;" if is_ref else ""
        ref_star = " ★" if is_ref else ""
        equiv_str = "1.00" if is_ref else f"{equiv:.2f}"

        rows_html += f"""
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:7px;">
            <div style="background:{bg_color}; color:{txt_color}; border-radius:50%;
                        width:26px; height:26px; display:flex; align-items:center;
                        justify-content:center; font-size:11px; font-weight:700; flex-shrink:0;">
                {rank + 1}
            </div>
            <div style="flex:2; font-size:13px; {name_style}">{label}{ref_star}</div>
            <div style="flex:3; background:rgba(255,255,255,0.08); border-radius:4px; height:14px; overflow:hidden;">
                <div style="width:{bar_width}%; height:100%; background:{bg_color};
                            border-radius:4px;"></div>
            </div>
            <div style="flex:1; text-align:right; font-family:monospace; font-size:13px; color:#ccc; padding-right:8px;">
                {norm_score:.2f}
            </div>
            <div style="flex:1; text-align:right; font-family:monospace; font-size:13px; color:#aaa;">
                {equiv_str}
            </div>
        </div>
        """

    st.html(header_html + rows_html)


def _group_summary(
    p_keys: list, t_keys: list,
    player_fields: dict, target_fields: dict, mode: str,
    effective_fn=None,
) -> str:
    """Build a compact summary string for an expander header from current session state."""
    p_prefix = f"dm_p_{mode}"
    t_prefix = f"dm_t_{mode}"

    p_vals = {f: st.session_state.get(_field_key(p_prefix, f), player_fields[f][1]) for f in p_keys}
    t_vals = {f: st.session_state.get(_field_key(t_prefix, f), target_fields[f][1]) for f in t_keys}

    if effective_fn is not None:
        effective = effective_fn(p_vals, t_vals)
        return f"Effective: {effective:.2f}×"

    # Fallback for groups without a defined effective multiplier (e.g. Base Attack)
    all_pct = all(f in _PCT_FIELDS or f in _SELECT_FIELDS for f in p_keys + t_keys)
    suf = "%" if all_pct else ""
    p_total = sum(p_vals.values())
    if not t_keys:
        return f"Player: {p_total:g}{suf}"
    t_total = sum(t_vals.values())
    net = p_total - t_total
    sign = "+" if net >= 0 else ""
    return f"Player: {p_total:g}{suf}  ·  Target: {t_total:g}{suf}  →  Net: {sign}{net:g}{suf}"


def _build_panel(store_key: str, apply_fn, label_prefix: str, mode: str, fields: dict):
    """Render select/load/delete/save controls for one build category (player or target)."""
    builds: dict = st.session_state[store_key]
    compatible = {k: v for k, v in builds.items() if v.get("mode") == mode}
    has_builds = bool(compatible)
    names = list(compatible.keys()) if has_builds else [f"No {mode} builds saved"]

    pending_key = f"{label_prefix}_pending_select"
    last_applied_key = f"{label_prefix}_last_applied"

    # Apply any pending selection written by the save handler in the previous run.
    # Must happen before the selectbox renders to avoid the post-instantiation write error.
    if pending_key in st.session_state and st.session_state[pending_key] in names:
        st.session_state[f"{label_prefix}_select"] = st.session_state.pop(pending_key)

    # --- Select & delete (always rendered for consistent height) ---
    col_sel, col_del = st.columns([5, 1])
    with col_sel:
        selected = st.selectbox(
            "Build", names, index=0, label_visibility="collapsed",
            key=f"{label_prefix}_select", disabled=not has_builds,
        )
    with col_del:
        if st.button("🗑️", use_container_width=True, key=f"{label_prefix}_del",
                     type="secondary", help="Delete build", disabled=not has_builds):
            del st.session_state[store_key][selected]
            st.rerun(scope="fragment")

    # Auto-apply when the selection changes (detected by comparing to last applied).
    # Runs in the fragment body rather than on_change so st.rerun(scope="app") reliably
    # triggers a full rerun that updates widgets outside the fragment.
    last_applied = st.session_state.get(last_applied_key)
    if has_builds and selected in compatible and selected != last_applied:
        apply_fn(compatible[selected])
        st.session_state[last_applied_key] = selected
        st.session_state[f"{label_prefix}_name"] = selected
        st.rerun(scope="app")

    # --- Save current as new build ---
    col_name, col_save = st.columns([3, 1])
    with col_name:
        new_name = st.text_input(
            "Name", placeholder=f"e.g. My {mode} build",
            label_visibility="collapsed", key=f"{label_prefix}_name"
        )
    with col_save:
        if st.button("💾", use_container_width=True, key=f"{label_prefix}_save", help="Save build"):
            name = new_name.strip()
            if not name:
                st.toast("Enter a build name.", icon="❌")
            else:
                overwrite = name in builds
                builds[name] = {
                    "mode": mode,
                    "stats": _read_from_session(fields, label_prefix),
                }
                # Write to a pending key — cannot write directly to the selectbox key
                # after it has already been instantiated in this run.
                st.session_state[pending_key] = name
                # Mark as last applied so saving doesn't trigger an auto-apply on next run.
                st.session_state[last_applied_key] = name
                st.toast(f"{'Updated' if overwrite else 'Saved'} '{name}'", icon="✅")
                st.rerun(scope="fragment")


# ---------------------------------------------------------------------------
# Build management — above mode radio + inputs so session state is set first.
# ---------------------------------------------------------------------------
if "player_builds" not in st.session_state:
    st.session_state["player_builds"] = {}
if "target_builds" not in st.session_state:
    st.session_state["target_builds"] = {}

@st.fragment
def _manage_builds_panel():
    # Peek at mode from session state (radio not yet rendered in main script)
    mode_now = st.session_state.get("dm_mode", "PVE")

    with st.expander("📁 Manage Builds"):

        # --- Upload ---
        uploaded = st.file_uploader(
            "Load builds from JSON", type=["json"], key="dm_uploader"
        )
        if uploaded is not None:
            file_id = f"{uploaded.name}_{uploaded.size}"
            if st.session_state.get("_last_loaded") != file_id:
                try:
                    data = json.load(uploaded)
                    n_player = n_target = 0

                    if "player_builds" in data or "target_builds" in data:
                        # Current format
                        for name, b in data.get("player_builds", {}).items():
                            st.session_state["player_builds"][name] = b
                            n_player += 1
                        for name, b in data.get("target_builds", {}).items():
                            st.session_state["target_builds"][name] = b
                            n_target += 1

                    elif "builds" in data:
                        # Legacy combined format — split into player + target
                        for name, b in data["builds"].items():
                            bmode = b.get("mode", "PVE")
                            p_fields, t_fields = _ALL_FIELDS[bmode]
                            if "player" in b:
                                st.session_state["player_builds"][name] = {
                                    "mode": bmode,
                                    "stats": {k: v for k, v in b["player"].items() if k in p_fields},
                                }
                                n_player += 1
                            if "target" in b:
                                st.session_state["target_builds"][name] = {
                                    "mode": bmode,
                                    "stats": {k: v for k, v in b["target"].items() if k in t_fields},
                                }
                                n_target += 1
                    else:
                        st.toast("Unrecognised file format.", icon="❌")

                    if n_player or n_target:
                        st.session_state["_last_loaded"] = file_id
                        st.toast(f"Loaded {n_player} player build(s) and {n_target} target build(s).", icon="✅")

                except Exception as e:
                    st.toast(f"Failed to load file: {e}", icon="❌")

        st.divider()

        col_p, col_t = st.columns(2)

        with col_p:
            st.markdown("**Player Builds**")
            _p_fields = _PVE_PLAYER_FIELDS if mode_now == "PVE" else _PVP_PLAYER_FIELDS
            _build_panel("player_builds", _apply_player_build, f"dm_p_{mode_now}", mode_now, _p_fields)

        with col_t:
            st.markdown("**Target Builds**")
            _t_fields = _PVE_TARGET_FIELDS if mode_now == "PVE" else _PVP_TARGET_FIELDS
            _build_panel("target_builds", _apply_target_build, f"dm_t_{mode_now}", mode_now, _t_fields)

        st.divider()

    # --- Download ---
    total = len(st.session_state["player_builds"]) + len(st.session_state["target_builds"])
    if total:
        dl_data = json.dumps({
            "player_builds": st.session_state["player_builds"],
            "target_builds": st.session_state["target_builds"],
        }, indent=2)
        st.download_button(
            f"Download builds JSON ({len(st.session_state['player_builds'])}P / "
            f"{len(st.session_state['target_builds'])}T)",
            data=dl_data, file_name="rag_builds.json",
            mime="application/json", use_container_width=True, key="dm_download",
        )

_manage_builds_panel()

# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------
col_mode, col_dmg = st.columns([1, 2])
with col_mode:
    mode = st.radio("Mode", ["PVE", "PVP"], horizontal=True, key="dm_mode")
with col_dmg:
    dmg_type = st.radio(
        "Damage Type", ["Crit", "Penetration"], horizontal=True, key="dm_dmg_type",
        help=(
            "Crit: damage multiplied by (Crit DMG Bonus − Target Crit DMG Reduc).  "
            "Penetration: non-crit hits — multiplier = 1 + PEN−DEF (or 1 + 2×(PEN−DEF) − 1.5 if PEN−DEF > 150%)."
        ),
    )

@st.fragment
def _stat_input_section():
    _mode     = st.session_state.get("dm_mode", "PVE")
    _dmg_type = st.session_state.get("dm_dmg_type", "Crit")
    _player_fields = _PVE_PLAYER_FIELDS if _mode == "PVE" else _PVP_PLAYER_FIELDS
    _target_fields = _PVE_TARGET_FIELDS if _mode == "PVE" else _PVP_TARGET_FIELDS
    _groups = _get_groups(_mode, _dmg_type)

    # Reset expander states when mode or damage type changes.
    _state_key = f"{_mode}_{_dmg_type}"
    if st.session_state.get("dm_state_key_prev") != _state_key:
        for _lbl in ["Base Attack", "Crit", "Penetration", "Final P.DMG",
                     "Size", "Element", "Race", "Final DMG", "PVP DMG"]:
            st.session_state.pop(f"dm_exp_{_lbl}", None)
        st.session_state["dm_state_key_prev"] = _state_key

    _player_vals: dict = {}
    _target_vals: dict = {}

    for _grp_label, _p_keys, _t_keys, _effective_fn in _groups:
        _exp_key = f"dm_exp_{_grp_label}"
        st.session_state.setdefault(_exp_key, False)

        # on_change fires before the rerun, so setting the key here guarantees
        # the expander re-renders as open when an input inside it changes.
        def _mark_open(_k=_exp_key):
            st.session_state[_k] = True

        _icon = _GROUP_ICONS.get(_grp_label, '')
        _summary = _group_summary(_p_keys, _t_keys, _player_fields, _target_fields, _mode, _effective_fn)
        with st.expander(f"{_icon} **{_grp_label}**  ·  {_summary}", expanded=st.session_state[_exp_key]):
            _col_a, _col_b = st.columns(2)
            with _col_a:
                st.markdown("**Player**")
                for _field in _p_keys:
                    _label, _default = _player_fields[_field]
                    _player_vals[_field] = _render_input(
                        _field, _label, _default, _field_key(f"dm_p_{_mode}", _field),
                        on_change=_mark_open,
                    )
            with _col_b:
                if _t_keys:
                    st.markdown("**Target**")
                for _field in _t_keys:
                    _label, _default = _target_fields[_field]
                    _target_vals[_field] = _render_input(
                        _field, _label, _default, _field_key(f"dm_t_{_mode}", _field),
                        on_change=_mark_open,
                    )

    # Publish current values so the Calculate button (outside the fragment) can read them.
    st.session_state["_dm_player_vals"] = _player_vals
    st.session_state["_dm_target_vals"] = _target_vals

_stat_input_section()

col_calc, col_reset, _ = st.columns([1, 1, 6])
with col_calc:
    _do_calculate = st.button("Calculate", key="dm_btn", type="primary", use_container_width=True)
with col_reset:
    if st.button("↺ Reset", use_container_width=True, help="Reset all inputs to default values"):
        _p_fields, _t_fields = _ALL_FIELDS[mode]
        for _f in _p_fields:
            st.session_state.pop(_field_key(f"dm_p_{mode}", _f), None)
        for _f in _t_fields:
            st.session_state.pop(_field_key(f"dm_t_{mode}", _f), None)
        st.rerun()
if _do_calculate:
    player_vals = st.session_state.get("_dm_player_vals", {})
    target_vals = st.session_state.get("_dm_target_vals", {})
    p_dec = _pct_to_decimal(player_vals)
    t_dec = _pct_to_decimal(target_vals)
    _dmg_type_param = "pen" if st.session_state.get("dm_dmg_type") == "Penetration" else "crit"
    multiplier = _calculate(mode, p_dec, t_dec, _dmg_type_param)
    weights = _weights(mode, p_dec, t_dec, _dmg_type_param)

    # Scale PCT fields so weights represent change-per-1-unit-of-user-input.
    weights = {k: (v * 0.01 if k in _PCT_FIELDS else v) for k, v in weights.items()}

    # Exclude static select-box fields from comparison charts
    weights = {k: v for k, v in weights.items() if k not in _SELECT_FIELDS}

    # Exclude the inactive damage-type stat from the chart
    if _dmg_type_param == "crit":
        weights.pop('total_final_pen', None)
    else:
        weights.pop('crit_dmg_bonus', None)

    p_fields, _ = _ALL_FIELDS[mode]
    labels_map = {field: label for field, (label, _) in p_fields.items()}
    positive_weights = {k: v for k, v in weights.items() if v > 0}

    # Persist results so reruns from the reference selectbox don't clear them.
    st.session_state["dm_results"] = {
        "multiplier":       multiplier,
        "weights":          weights,
        "labels_map":       labels_map,
        "positive_weights": positive_weights,
        "best_stat":        max(positive_weights, key=positive_weights.get),
    }
    # Reset reference stat so it defaults to the best stat on new calculations.
    st.session_state.pop("dm_ref", None)

if "dm_results" in st.session_state:
    res              = st.session_state["dm_results"]
    multiplier       = res["multiplier"]
    weights          = res["weights"]
    labels_map       = res["labels_map"]
    positive_weights = res["positive_weights"]
    best_stat        = res["best_stat"]

    # Hero metric card
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(231,76,60,0.15) 0%, rgba(26,26,46,0.6) 100%);
                border: 1px solid rgba(231,76,60,0.5); border-radius: 12px;
                padding: 20px 32px; text-align: center; margin: 16px 0;">
        <div style="font-size: 12px; color: #aaa; letter-spacing: 2px;
                    text-transform: uppercase; margin-bottom: 4px;">
            Damage Multiplier
        </div>
        <div style="font-size: 56px; font-weight: 800; color: #e74c3c; line-height: 1.1;">
            {multiplier:,.2f}
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    st.markdown("#### Stat Priority")
    st.caption(
        "Bars show relative priority vs the selected reference stat (★). "
        "Score is always normalized to the absolute best stat = 1.00. "
        "The equivalence column shows how many points of each stat equal 1 point of the reference."
    )
    # Best stat callout
    st.markdown(f"""
    <div style="background: rgba(46,204,113,0.1); border-left: 3px solid #2ecc71;
                border-radius: 0 6px 6px 0; padding: 8px 14px; margin-bottom: 12px;">
        <span style="color:#2ecc71; font-weight:700;">▲ Top priority: {labels_map[best_stat]}</span>
        <span style="color:#aaa; font-size:13px;"> — invest here for the greatest DPS gain per point.</span>
    </div>
    """, unsafe_allow_html=True)

    ref_options = sorted(positive_weights.keys(), key=lambda k: labels_map[k])
    current_ref = st.session_state.get("dm_ref", best_stat)
    if current_ref not in ref_options:
        current_ref = best_stat
    reference = st.selectbox(
        "Reference stat for equivalence", options=ref_options,
        format_func=lambda k: labels_map[k],
        index=ref_options.index(current_ref),
        key="dm_ref",
    )
    _render_combined(positive_weights, labels_map, reference)


# ---------------------------------------------------------------------------
# Build Comparison Panel
# ---------------------------------------------------------------------------
st.divider()
st.markdown("### Build Comparison")
st.caption(
    "Compare damage multipliers for saved player builds against a fixed target. "
    "Select a target, pick one or more player builds, and the chart updates automatically."
)

col_cmp_mode, col_cmp_dmg = st.columns([1, 2])
with col_cmp_mode:
    cmp_mode = st.radio("Comparison Mode", ["PVE", "PVP"], horizontal=True, key="cmp_mode")
with col_cmp_dmg:
    cmp_dmg_type = st.radio("Damage Type", ["Crit", "Penetration"], horizontal=True, key="cmp_dmg_type")

_cmp_p_fields = _PVE_PLAYER_FIELDS if cmp_mode == "PVE" else _PVP_PLAYER_FIELDS
_cmp_t_fields = _PVE_TARGET_FIELDS if cmp_mode == "PVE" else _PVP_TARGET_FIELDS

_cmp_player_builds = {
    k: v for k, v in st.session_state.get("player_builds", {}).items()
    if v.get("mode") == cmp_mode
}
_cmp_target_builds = {
    k: v for k, v in st.session_state.get("target_builds", {}).items()
    if v.get("mode") == cmp_mode
}

col_cmp_t, col_cmp_p = st.columns(2)

with col_cmp_t:
    st.markdown("**Target**")
    _target_opts = ["— Current target —"] + list(_cmp_target_builds.keys())
    _sel_target = st.selectbox("Target", _target_opts, label_visibility="collapsed", key="cmp_target_sel")

with col_cmp_p:
    st.markdown("**Player Builds**")
    if _cmp_player_builds:
        _sel_builds = st.multiselect(
            "Player builds", options=list(_cmp_player_builds.keys()),
            label_visibility="collapsed", key="cmp_build_sel",
        )
    else:
        st.caption(f"No {cmp_mode} player builds saved.")
        _sel_builds = []

if _sel_builds:
    # Resolve target stats
    if _sel_target == "— Current target —":
        _t_raw = _read_from_session(_cmp_t_fields, f"dm_t_{cmp_mode}")
    else:
        _t_raw = _read_from_build(_cmp_target_builds[_sel_target]["stats"], _cmp_t_fields)
    _t_dec = _pct_to_decimal(_t_raw)

    # Calculate multiplier for each selected build
    _cmp_dmg_param = "pen" if cmp_dmg_type == "Penetration" else "crit"
    _cmp_results = {}
    for _bname in _sel_builds:
        _p_raw = _read_from_build(_cmp_player_builds[_bname]["stats"], _cmp_p_fields)
        _p_dec = _pct_to_decimal(_p_raw)
        _cmp_results[_bname] = _calculate(cmp_mode, _p_dec, _t_dec, _cmp_dmg_param)

    _sorted = sorted(_cmp_results.items(), key=lambda x: x[1], reverse=True)
    _names  = [k for k, _ in _sorted]
    _values = [v for _, v in _sorted]
    _max    = max(_values)
    _colors = _gradient_colors([v / _max for v in _values])

    _cmp_fig = _make_bar_chart(
        _values, _names, _colors,
        x_title="Damage Multiplier",
        hover_tpl='<b>%{y}</b><br>Multiplier: %{x:,.2f}<extra></extra>',
    )
    st.plotly_chart(_cmp_fig, use_container_width=True)
else:
    st.info(f"Select at least one {cmp_mode} player build above to see the comparison.")
