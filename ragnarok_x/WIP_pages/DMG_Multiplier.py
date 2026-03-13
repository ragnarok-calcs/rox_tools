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

# Union of all player/target fields across both modes (used for build storage).
_ALL_PLAYER_FIELDS: dict = {}
for _f, _v in {**_PVE_PLAYER_FIELDS, **_PVP_PLAYER_FIELDS}.items():
    _ALL_PLAYER_FIELDS.setdefault(_f, _v)

_ALL_TARGET_FIELDS: dict = {}
for _f, _v in {**_PVE_TARGET_FIELDS, **_PVP_TARGET_FIELDS}.items():
    _ALL_TARGET_FIELDS.setdefault(_f, _v)

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


def _get_groups(mode: str) -> list:
    """Return stat input groups with both Crit and Pen always present."""
    base = _PVE_GROUPS if mode == "PVE" else _PVP_GROUPS
    result = []
    for g in base:
        if g[0] == "Crit":
            result.append(g)
            result.append(_PEN_GROUP)
        else:
            result.append(g)
    return result


# Grouped layout: list of (header, [player_fields], [target_fields], effective_fn)
_PVE_GROUPS = [
    ('Base Attack', ['patk', 'pdmg_bonus', 'pdmg_bonus_pct'],                      ['pdmg_reduc'],  None),
    ('Crit',        ['crit_dmg_bonus'],                                             ['crit_dmg_reduc'],
        lambda p, t: max(p['crit_dmg_bonus'] / 100 - t['crit_dmg_reduc'] / 100, 0.2)),
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
        lambda p, t: max(p['crit_dmg_bonus'] / 100 - t['crit_dmg_reduc'] / 100, 0.2)),
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


def _pct_to_decimal(vals: dict) -> dict:
    """Convert integer-percentage fields to their decimal equivalents for formula use."""
    return {k: v / 100.0 if k in _PCT_FIELDS else v for k, v in vals.items()}


def _calculate(mode: str, p_dec: dict, t_dec: dict, dmg_type: str,
               attack_mult: int = 8) -> float:
    """Dispatch to the correct PVE/PVP multiplier calculation."""
    if mode == "PVE":
        return pve_calculate_multiplier(PVEPlayerStats(**p_dec), PVETargetStats(**t_dec), dmg_type, attack_mult)
    return pvp_calculate_multiplier(PVPPlayerStats(**p_dec), PVPTargetStats(**t_dec), dmg_type, attack_mult)


def _weights(mode: str, p_dec: dict, t_dec: dict, dmg_type: str,
             attack_mult: int = 8) -> dict[str, float]:
    """Dispatch to the correct PVE/PVP modifier weights calculation."""
    if mode == "PVE":
        return pve_modifier_weights(PVEPlayerStats(**p_dec), PVETargetStats(**t_dec), dmg_type, attack_mult)
    return pvp_modifier_weights(PVPPlayerStats(**p_dec), PVPTargetStats(**t_dec), dmg_type, attack_mult)


# ---------------------------------------------------------------------------
# Build apply / read helpers
# ---------------------------------------------------------------------------
def _apply_player_build(build: dict):
    """Apply a player build's stats to widget keys for BOTH PVE and PVP modes."""
    stats = build.get("stats", {})
    for m in ("PVE", "PVP"):
        fields = _PVE_PLAYER_FIELDS if m == "PVE" else _PVP_PLAYER_FIELDS
        for field, (_, default) in fields.items():
            value = stats.get(field, default)
            v = int(value) if field in _SELECT_FIELDS else float(value)
            st.session_state[_field_key(f"dm_p_{m}", field)] = v


def _apply_target_build(build: dict):
    """Apply a target build's stats to widget keys for BOTH PVE and PVP modes."""
    stats = build.get("stats", {})
    for m in ("PVE", "PVP"):
        fields = _PVE_TARGET_FIELDS if m == "PVE" else _PVP_TARGET_FIELDS
        for field, (_, default) in fields.items():
            value = stats.get(field, default)
            st.session_state[_field_key(f"dm_t_{m}", field)] = float(value)


def _apply_player_defaults():
    """Reset all player widget keys to their defaults across both modes."""
    for m in ("PVE", "PVP"):
        fields = _PVE_PLAYER_FIELDS if m == "PVE" else _PVP_PLAYER_FIELDS
        for f, (_, default) in fields.items():
            v = int(default) if f in _SELECT_FIELDS else float(default)
            st.session_state[_field_key(f"dm_p_{m}", f)] = v


def _apply_target_defaults():
    """Reset all target widget keys to their defaults across both modes."""
    for m in ("PVE", "PVP"):
        fields = _PVE_TARGET_FIELDS if m == "PVE" else _PVP_TARGET_FIELDS
        for f, (_, default) in fields.items():
            st.session_state[_field_key(f"dm_t_{m}", f)] = float(default)


def _read_all_player_stats() -> dict:
    """Read all player stats from widget keys; current mode takes precedence for shared fields."""
    result = {}
    current_mode = st.session_state.get("dm_mode", "PVE")
    other_mode   = "PVP" if current_mode == "PVE" else "PVE"
    for m in (other_mode, current_mode):   # current mode overwrites last
        fields = _PVE_PLAYER_FIELDS if m == "PVE" else _PVP_PLAYER_FIELDS
        for f, (_, default) in fields.items():
            result[f] = st.session_state.get(_field_key(f"dm_p_{m}", f), default)
    return result


def _read_all_target_stats() -> dict:
    """Read all target stats from widget keys; current mode takes precedence for shared fields."""
    result = {}
    current_mode = st.session_state.get("dm_mode", "PVE")
    other_mode   = "PVP" if current_mode == "PVE" else "PVE"
    for m in (other_mode, current_mode):
        fields = _PVE_TARGET_FIELDS if m == "PVE" else _PVP_TARGET_FIELDS
        for f, (_, default) in fields.items():
            result[f] = st.session_state.get(_field_key(f"dm_t_{m}", f), default)
    return result


def _read_from_session(fields: dict, key_prefix: str) -> dict:
    return {
        field: st.session_state.get(_field_key(key_prefix, field), default)
        for field, (_, default) in fields.items()
    }


def _read_from_build(build_stats: dict, fields: dict) -> dict:
    return {f: build_stats.get(f, default) for f, (_, default) in fields.items()}


# ---------------------------------------------------------------------------
# Chart / display helpers
# ---------------------------------------------------------------------------
def _make_bar_chart(
    values: list, labels: list, colors: list,
    x_title: str = "", hover_tpl: str = "", right_margin: int = 80,
) -> go.Figure:
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


def _gradient_colors(values: list) -> list:
    anchors = [
        (1.0, (255, 215,   0)),
        (0.5, ( 46, 204, 113)),
        (0.0, ( 93, 173, 226)),
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
    if rank == 0:
        return ('#FFD700', '#1a1a1a')
    elif rank <= 2:
        return ('#2ecc71', '#ffffff')
    else:
        return ('#5dade2', '#ffffff')


def _render_combined(weights: dict[str, float], labels: dict[str, str], reference: str):
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
    p_prefix = f"dm_p_{mode}"
    t_prefix = f"dm_t_{mode}"
    p_vals = {f: st.session_state.get(_field_key(p_prefix, f), player_fields[f][1]) for f in p_keys}
    t_vals = {f: st.session_state.get(_field_key(t_prefix, f), target_fields[f][1]) for f in t_keys}
    if effective_fn is not None:
        effective = effective_fn(p_vals, t_vals)
        return f"Effective: {effective:.2f}×"
    all_pct = all(f in _PCT_FIELDS or f in _SELECT_FIELDS for f in p_keys + t_keys)
    suf = "%" if all_pct else ""
    p_total = sum(p_vals.values())
    if not t_keys:
        return f"Player: {p_total:g}{suf}"
    t_total = sum(t_vals.values())
    net = p_total - t_total
    sign = "+" if net >= 0 else ""
    return f"Player: {p_total:g}{suf}  ·  Target: {t_total:g}{suf}  →  Net: {sign}{net:g}{suf}"


# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------
if "player_builds" not in st.session_state:
    st.session_state["player_builds"] = {}
if "target_builds" not in st.session_state:
    st.session_state["target_builds"] = {}

# ---------------------------------------------------------------------------
# Sidebar — Build Manager
# ---------------------------------------------------------------------------
def _sidebar_save_row(side: str, label: str):
    """Render a name input + save button for player ('p') or target ('t') builds."""
    col_name, col_save = st.columns([3, 1])
    with col_name:
        new_name = st.text_input(f"{label} build name", placeholder="Build name",
                                 key=f"dm_sb_{side}_name", label_visibility="collapsed")
    with col_save:
        if st.button("💾", key=f"dm_sb_{side}_save", help=f"Save current {label} stats",
                     use_container_width=True):
            name = new_name.strip()
            if not name:
                st.toast("Enter a name.", icon="❌")
            elif name == "Default":
                st.toast('"Default" is reserved.', icon="❌")
            else:
                store_key = "player_builds" if side == "p" else "target_builds"
                overwrite = name in st.session_state[store_key]
                stats = _read_all_player_stats() if side == "p" else _read_all_target_stats()
                st.session_state[store_key][name] = {"stats": stats}
                st.session_state[f"dm_active_{side}_build"] = name
                st.session_state["_sb_file_loaded"] = True
                st.toast(f"{'Updated' if overwrite else 'Saved'} '{name}'", icon="✅")
                st.rerun()


with st.sidebar:
    st.header("Builds")

    if not st.session_state.get("_sb_file_loaded"):
        # ── Upload state ──────────────────────────────────────────────────
        uploaded_files = st.file_uploader(
            "Load builds from JSON", type=["json"],
            key="dm_uploader", accept_multiple_files=True,
        )
        if uploaded_files:
            last_name = ""
            for uploaded in uploaded_files:
                try:
                    data = json.load(uploaded)
                    n_player = n_target = 0
                    if "player_builds" in data or "target_builds" in data:
                        for name, b in data.get("player_builds", {}).items():
                            st.session_state["player_builds"][name] = {"stats": b.get("stats", b)}
                            n_player += 1
                        for name, b in data.get("target_builds", {}).items():
                            st.session_state["target_builds"][name] = {"stats": b.get("stats", b)}
                            n_target += 1
                    elif "builds" in data:
                        for name, b in data["builds"].items():
                            if "player" in b:
                                st.session_state["player_builds"][name] = {
                                    "stats": {k: v for k, v in b["player"].items()
                                              if k in _ALL_PLAYER_FIELDS},
                                }
                                n_player += 1
                            if "target" in b:
                                st.session_state["target_builds"][name] = {
                                    "stats": {k: v for k, v in b["target"].items()
                                              if k in _ALL_TARGET_FIELDS},
                                }
                                n_target += 1
                    else:
                        st.toast(f"{uploaded.name}: unrecognised format.", icon="❌")
                        continue
                    last_name = uploaded.name
                    st.toast(f"{uploaded.name}: loaded {n_player}P / {n_target}T.", icon="✅")
                except Exception as e:
                    st.toast(f"{uploaded.name}: {e}", icon="❌")
            if last_name:
                st.session_state["_sb_file_loaded"] = True
                st.session_state["_sb_loaded_filename"] = last_name
                st.rerun()

    else:
        # ── Loaded state ──────────────────────────────────────────────────
        loaded_name = st.session_state.get("_sb_loaded_filename", "builds")
        st.caption(f"📄 {loaded_name}")

        total = (len(st.session_state["player_builds"])
                 + len(st.session_state["target_builds"]))
        if total:
            dl_data = json.dumps({
                "player_builds": st.session_state["player_builds"],
                "target_builds": st.session_state["target_builds"],
            }, indent=2)
            st.download_button(
                f"⬇ Export builds ({len(st.session_state['player_builds'])}P"
                f" / {len(st.session_state['target_builds'])}T)",
                data=dl_data, file_name="rag_builds.json",
                mime="application/json", use_container_width=True, key="dm_download",
            )

        st.divider()

        # ── Player Builds ─────────────────────────────────────────────────
        st.subheader("Player Builds")
        _sidebar_save_row("p", "Player")
        active_p = st.session_state.get("dm_active_p_build")
        for bname, build in list(st.session_state["player_builds"].items()):
            is_active = bname == active_p
            col_n, col_apply, col_del = st.columns([4, 1, 1])
            with col_n:
                if is_active:
                    st.markdown(f"**▸ {bname}**")
                else:
                    st.markdown(bname)
            with col_apply:
                if st.button("▶", key=f"apply_p_{bname}", help=f"Apply {bname}",
                             use_container_width=True):
                    _apply_player_build(build)
                    st.session_state["dm_active_p_build"] = bname
                    st.rerun()
            with col_del:
                if st.button("🗑️", key=f"del_p_{bname}", use_container_width=True):
                    del st.session_state["player_builds"][bname]
                    if active_p == bname:
                        st.session_state.pop("dm_active_p_build", None)
                    st.rerun()

        st.divider()

        # ── Target Builds ─────────────────────────────────────────────────
        st.subheader("Target Builds")
        _sidebar_save_row("t", "Target")
        active_t = st.session_state.get("dm_active_t_build")
        for bname, build in list(st.session_state["target_builds"].items()):
            is_active = bname == active_t
            col_n, col_apply, col_del = st.columns([4, 1, 1])
            with col_n:
                if is_active:
                    st.markdown(f"**▸ {bname}**")
                else:
                    st.markdown(bname)
            with col_apply:
                if st.button("▶", key=f"apply_t_{bname}", help=f"Apply {bname}",
                             use_container_width=True):
                    _apply_target_build(build)
                    st.session_state["dm_active_t_build"] = bname
                    st.rerun()
            with col_del:
                if st.button("🗑️", key=f"del_t_{bname}", use_container_width=True):
                    del st.session_state["target_builds"][bname]
                    if active_t == bname:
                        st.session_state.pop("dm_active_t_build", None)
                    st.rerun()

# ---------------------------------------------------------------------------
# Page layout — mode / damage type / attack type radios
# ---------------------------------------------------------------------------
col_mode, col_dmg, col_atk = st.columns([1, 2, 2])
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
with col_atk:
    atk_type = st.radio(
        "Attack Type", ["Normal Attack", "Skill Attack"], horizontal=True, key="dm_atk_type",
        help="Normal Attack: attack_mult=8, P/MATK%=100, hits=1.  Skill Attack: attack_mult=16, user-defined P/MATK% and hits.",
    )

_is_skill = atk_type == "Skill Attack"
col_pmatk, col_hits, _ = st.columns([1, 1, 4])
with col_pmatk:
    pmatk_pct = st.number_input(
        "P/MATK% Modifier", min_value=0, max_value=99999, value=100, step=1,
        key="dm_pmatk_pct", disabled=not _is_skill,
        help="Skill P/MATK% coefficient applied to P.ATK in the base formula (100 = 1×).",
    )
with col_hits:
    num_hits = st.number_input(
        "Number of Hits", min_value=1, max_value=99, value=1, step=1,
        key="dm_num_hits", disabled=not _is_skill,
        help="Number of times the skill hits. Final damage = single-hit multiplier × hits.",
    )


@st.fragment
def _stat_input_section():
    _mode     = st.session_state.get("dm_mode", "PVE")
    _dmg_type = st.session_state.get("dm_dmg_type", "Crit")
    _player_fields = _PVE_PLAYER_FIELDS if _mode == "PVE" else _PVP_PLAYER_FIELDS
    _target_fields = _PVE_TARGET_FIELDS if _mode == "PVE" else _PVP_TARGET_FIELDS
    _groups = _get_groups(_mode)

    # Reset expander states when mode changes
    _prev_mode = st.session_state.get("dm_mode_prev")
    if _prev_mode != _mode:
        for _lbl in ["Base Attack", "Crit", "Penetration", "Final P.DMG",
                     "Size", "Element", "Race", "Final DMG", "PVP DMG"]:
            st.session_state.pop(f"dm_exp_{_lbl}", None)
        st.session_state["dm_mode_prev"] = _mode

    _player_vals: dict = {}
    _target_vals: dict = {}

    for _grp_label, _p_keys, _t_keys, _effective_fn in _groups:
        _exp_key = f"dm_exp_{_grp_label}"
        st.session_state.setdefault(_exp_key, False)

        def _mark_open(_k=_exp_key):
            if not st.session_state.get("_dm_resetting"):
                st.session_state[_k] = True

        _icon    = _GROUP_ICONS.get(_grp_label, '')
        _summary = _group_summary(_p_keys, _t_keys, _player_fields, _target_fields, _mode, _effective_fn)
        _header  = f"{_icon} **{_grp_label}**  ·  {_summary}"
        with st.expander(_header, expanded=st.session_state[_exp_key]):
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

    st.session_state["_dm_player_vals"] = _player_vals
    st.session_state["_dm_target_vals"] = _target_vals
    st.session_state.pop("_dm_resetting", None)

_stat_input_section()


def _reset_inputs():
    """Reset inputs to the currently active build (or defaults if none is active)."""
    active_p = st.session_state.get("dm_active_p_build")
    if active_p and active_p in st.session_state.get("player_builds", {}):
        _apply_player_build(st.session_state["player_builds"][active_p])
    else:
        _apply_player_defaults()

    active_t = st.session_state.get("dm_active_t_build")
    if active_t and active_t in st.session_state.get("target_builds", {}):
        _apply_target_build(st.session_state["target_builds"][active_t])
    else:
        _apply_target_defaults()

    st.session_state["_dm_resetting"] = True
    st.session_state.pop("dm_results", None)


col_calc, col_reset, _ = st.columns([1, 1, 6])
with col_calc:
    _do_calculate = st.button("Calculate", key="dm_btn", type="primary", use_container_width=True)
with col_reset:
    st.button("↺ Reset", use_container_width=True,
              help="Reset inputs to the currently selected build",
              on_click=_reset_inputs)

if _do_calculate:
    player_vals = st.session_state.get("_dm_player_vals", {})
    target_vals = st.session_state.get("_dm_target_vals", {})
    p_dec = _pct_to_decimal(player_vals)
    t_dec = _pct_to_decimal(target_vals)
    _dmg_type_param = "pen" if st.session_state.get("dm_dmg_type") == "Penetration" else "crit"
    _is_skill_calc  = st.session_state.get("dm_atk_type") == "Skill Attack"
    _attack_mult    = 16 if _is_skill_calc else 8
    _pmatk_pct      = st.session_state.get("dm_pmatk_pct", 100) if _is_skill_calc else 100
    _num_hits       = st.session_state.get("dm_num_hits", 1) if _is_skill_calc else 1
    p_dec = dict(p_dec)
    p_dec['patk'] = p_dec['patk'] * _pmatk_pct / 100
    multiplier = _calculate(mode, p_dec, t_dec, _dmg_type_param, _attack_mult) * _num_hits
    weights    = _weights(mode, p_dec, t_dec, _dmg_type_param, _attack_mult)

    # Scale PCT fields so weights represent change-per-1-unit-of-user-input
    weights = {k: (v * 0.01 if k in _PCT_FIELDS else v) for k, v in weights.items()}
    # Exclude static select-box fields
    weights = {k: v for k, v in weights.items() if k not in _SELECT_FIELDS}
    # Exclude the inactive damage-type stat
    if _dmg_type_param == "crit":
        weights.pop('total_final_pen', None)
    else:
        weights.pop('crit_dmg_bonus', None)

    p_fields, _ = _ALL_FIELDS[mode]
    labels_map = {field: label for field, (label, _) in p_fields.items()}
    positive_weights = {k: v for k, v in weights.items() if v > 0}

    st.session_state["dm_results"] = {
        "multiplier":       multiplier,
        "weights":          weights,
        "labels_map":       labels_map,
        "positive_weights": positive_weights,
        "best_stat":        max(positive_weights, key=positive_weights.get),
        "num_hits":         _num_hits,
    }
    st.session_state.pop("dm_ref", None)

if "dm_results" in st.session_state:
    res              = st.session_state["dm_results"]
    multiplier       = res["multiplier"]
    weights          = res["weights"]
    labels_map       = res["labels_map"]
    positive_weights = res["positive_weights"]
    best_stat        = res["best_stat"]

    _res_atk_type = st.session_state.get("dm_atk_type", "Normal Attack")
    _res_hits     = res.get("num_hits", 1)
    _res_subtitle = _res_atk_type + (f"  ·  {_res_hits} hit{'s' if _res_hits != 1 else ''}" if _res_hits > 1 else "")
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(231,76,60,0.15) 0%, rgba(26,26,46,0.6) 100%);
                border: 1px solid rgba(231,76,60,0.5); border-radius: 12px;
                padding: 20px 32px; text-align: center; margin: 16px 0;">
        <div style="font-size: 12px; color: #aaa; letter-spacing: 2px;
                    text-transform: uppercase; margin-bottom: 4px;">
            Damage Multiplier  ·  {_res_subtitle}
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

# All builds now work across modes — no mode filtering
_cmp_player_builds = st.session_state.get("player_builds", {})
_cmp_target_builds = st.session_state.get("target_builds", {})

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
        st.caption("No player builds saved.")
        _sel_builds = []

if _sel_builds:
    if _sel_target == "— Current target —":
        _t_raw = _read_from_session(_cmp_t_fields, f"dm_t_{cmp_mode}")
    else:
        _t_raw = _read_from_build(_cmp_target_builds[_sel_target]["stats"], _cmp_t_fields)
    _t_dec = _pct_to_decimal(_t_raw)

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
    st.info("Select at least one player build above to see the comparison.")