import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
import streamlit as st
import plotly.graph_objects as go
from multiplier_stats import (
    PVEPlayerStats, PVETargetStats, pve_calculate_multiplier, pve_modifier_weights,
    PVPPlayerStats, PVPTargetStats, pvp_calculate_multiplier, pvp_modifier_weights,
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
    'patk':                 ('P.ATK',                  1000.0),
    'crit_dmg_bonus':       ('Crit DMG Bonus %',        200),
    'pdmg_bonus':           ('P.DMG Bonus',             0.0),
    'pdmg_bonus_pct':       ('P.DMG Bonus%',            0.0),
    'final_pdmg_bonus':     ('Final P.DMG Bonus %',     0),
    'elemental_counter':    ('Elemental Counter %',      100),
    'element_enhance':      ('Element Enhance %',        0),
    'bonus_dmg_element':    ('Bonus DMG to Element',     0.0),
    'bonus_dmg_race':       ('Bonus DMG to Race %',      0),
    'final_dmg_bonus':      ('Final DMG Bonus %',        0),
    'weapon_size_modifier': ('Weapon Size Modifier %',   100),
    'size_enhance':         ('Size Enhance %',           0),
}
_PVE_TARGET_FIELDS = {
    'crit_dmg_reduc':   ('Crit DMG Reduction %',     0),
    'pdmg_reduc':       ('P.DMG Reduction',           0.0),
    'final_pdmg_reduc': ('Final P.DMG Reduction %',   0),
    'final_dmg_reduc':  ('Final DMG Reduction %',     0),
}
_PVP_PLAYER_FIELDS = {
    'patk':                 ('P.ATK',                  1000.0),
    'crit_dmg_bonus':       ('Crit DMG Bonus %',        200),
    'pdmg_bonus':           ('P.DMG Bonus',             0.0),
    'pdmg_bonus_pct':       ('P.DMG Bonus%',            0.0),
    'final_pdmg_bonus':     ('Final P.DMG Bonus %',     0),
    'weapon_size_modifier': ('Weapon Size Modifier %',   100),
    'size_enhance':         ('Size Enhance %',           0),
    'bonus_dmg_race':       ('Bonus DMG to Race %',      0),
    'elemental_counter':    ('Elemental Counter %',      100),
    'element_enhance':      ('Element Enhance %',        0),
    'final_dmg_bonus':      ('Final DMG Bonus %',        0),
    'pvp_final_pdmg_bonus': ('PVP Final P.DMG Bonus %',  0),
    'pvp_pdmg_bonus':       ('PVP P.DMG Bonus',         0.0),
}
_PVP_TARGET_FIELDS = {
    'crit_dmg_reduc':       ('Crit DMG Reduction %',        0),
    'pdmg_reduc':           ('P.DMG Reduction',             0.0),
    'final_pdmg_reduc':     ('Final P.DMG Reduction %',     0),
    'element_resist':       ('Element Resist %',             0),
    'size_reduc':           ('Size Reduction %',             0),
    'race_reduc':           ('Race Reduction %',             0),
    'final_dmg_reduc':      ('Final DMG Reduction %',        0),
    'pvp_pdmg_reduc':       ('PVP P.DMG Reduction',          0.0),
    'pvp_final_pdmg_reduc': ('PVP Final P.DMG Reduction %',  0),
}

_ALL_FIELDS = {
    'PVE': (_PVE_PLAYER_FIELDS, _PVE_TARGET_FIELDS),
    'PVP': (_PVP_PLAYER_FIELDS, _PVP_TARGET_FIELDS),
}

# Fields whose UI values are integer percentages (e.g. 20 → 0.20 in the formula).
_PCT_FIELDS = {
    'crit_dmg_bonus', 'final_pdmg_bonus', 'weapon_size_modifier', 'size_enhance',
    'bonus_dmg_race', 'elemental_counter', 'element_enhance',
    'final_dmg_bonus', 'pvp_final_pdmg_bonus',
    # Target reductions
    'crit_dmg_reduc', 'final_pdmg_reduc', 'element_resist', 'size_reduc',
    'race_reduc', 'final_dmg_reduc', 'pvp_final_pdmg_reduc',
}

# Fields rendered as selectboxes: {field: [option_ints]}
_SELECT_FIELDS = {
    'weapon_size_modifier': [75, 100],
    'elemental_counter':    [0, 25, 50, 70, 75, 90, 100, 125, 150, 175],
}

# Grouped layout: list of (header, [player_fields], [target_fields])
_PVE_GROUPS = [
    ('Base Attack', ['patk', 'pdmg_bonus', 'pdmg_bonus_pct'],                      ['pdmg_reduc']),
    ('Crit',        ['crit_dmg_bonus'],                                             ['crit_dmg_reduc']),
    ('Final P.DMG', ['final_pdmg_bonus'],                                           ['final_pdmg_reduc']),
    ('Size',        ['weapon_size_modifier', 'size_enhance'],                       []),
    ('Element',     ['elemental_counter', 'element_enhance', 'bonus_dmg_element'],  []),
    ('Race',        ['bonus_dmg_race'],                                             []),
    ('Final DMG',   ['final_dmg_bonus'],                                            ['final_dmg_reduc']),
]
_PVP_GROUPS = [
    ('Base Attack', ['patk', 'pdmg_bonus', 'pdmg_bonus_pct'],                      ['pdmg_reduc']),
    ('Crit',        ['crit_dmg_bonus'],                                             ['crit_dmg_reduc']),
    ('Final P.DMG', ['final_pdmg_bonus'],                                           ['final_pdmg_reduc']),
    ('Size',        ['weapon_size_modifier', 'size_enhance'],                       ['size_reduc']),
    ('Element',     ['elemental_counter', 'element_enhance'],                       ['element_resist']),
    ('Race',        ['bonus_dmg_race'],                                             ['race_reduc']),
    ('Final DMG',   ['final_dmg_bonus'],                                            ['final_dmg_reduc']),
    ('PVP DMG',     ['pvp_pdmg_bonus', 'pvp_final_pdmg_bonus'],                    ['pvp_pdmg_reduc', 'pvp_final_pdmg_reduc']),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _field_key(prefix: str, field: str) -> str:
    return f"{prefix}_{field}"


def _render_input(field: str, label: str, default, key: str):
    if field in _SELECT_FIELDS:
        options = _SELECT_FIELDS[field]
        return st.selectbox(
            label, options=options, index=options.index(int(default)),
            format_func=lambda x: f"{x}%", key=key,
        )
    elif field in _PCT_FIELDS:
        return st.number_input(label, value=int(default), min_value=0, step=1, key=key)
    else:
        return st.number_input(label, value=default, min_value=0.0, key=key)


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


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    max_w = max(abs(v) for v in weights.values())
    if max_w == 0:
        return {k: 0.0 for k in weights}
    return {k: v / max_w for k, v in weights.items()}


def _weight_chart(weights: dict[str, float], labels: dict[str, str]) -> go.Figure:
    norm = _normalize_weights(weights)
    sorted_items = sorted(norm.items(), key=lambda x: x[1], reverse=True)
    readable = [labels[k] for k, _ in sorted_items]
    values = [v for _, v in sorted_items]
    raw_values = [weights[k] for k, _ in sorted_items]
    colors = ['#2ecc71' if v >= 0 else '#e74c3c' for v in values]

    fig = go.Figure(go.Bar(
        x=values, y=readable, orientation='h',
        marker_color=colors, customdata=raw_values,
        hovertemplate='<b>%{y}</b><br>Relative weight: %{x:.3f}<br>Raw weight: %{customdata:.4f}<extra></extra>',
    ))
    fig.update_layout(
        xaxis=dict(title="Relative weight (best stat = 1.0)", range=[0, 1.05]),
        yaxis=dict(autorange='reversed'),
        margin=dict(l=0, r=20, t=20, b=40),
        height=80 + 36 * len(weights),
    )
    return fig


def _render_equivalence(weights: dict[str, float], labels: dict[str, str], reference: str):
    ref_w = weights[reference]
    sorted_items = sorted(
        [(k, v) for k, v in weights.items() if v > 0],
        key=lambda x: x[1], reverse=True,
    )
    hdr_name, hdr_bar, hdr_val = st.columns([3, 5, 2])
    hdr_name.caption("Stat")
    hdr_bar.caption("Relative priority")
    hdr_val.caption(f"Per 1 {labels[reference]}")
    for field, w in sorted_items:
        col_name, col_bar, col_val = st.columns([3, 5, 2])
        col_name.markdown(f"**{labels[field]}**")
        col_bar.progress(min(w / ref_w, 1.0))
        col_val.markdown(f"`{ref_w / w:.2f}`")


def _group_summary(
    p_keys: list, t_keys: list,
    player_fields: dict, target_fields: dict, mode: str,
) -> str:
    """Build a compact summary string for an expander header from current session state."""
    p_prefix = f"dm_p_{mode}"
    t_prefix = f"dm_t_{mode}"
    all_pct = all(f in _PCT_FIELDS or f in _SELECT_FIELDS for f in p_keys + t_keys)
    suf = "%" if all_pct else ""

    p_total = sum(
        st.session_state.get(_field_key(p_prefix, f), player_fields[f][1]) for f in p_keys
    )
    if not t_keys:
        return f"Player: {p_total:g}{suf}"

    t_total = sum(
        st.session_state.get(_field_key(t_prefix, f), target_fields[f][1]) for f in t_keys
    )
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
mode = st.radio("Mode", ["PVE", "PVP"], horizontal=True, key="dm_mode")

player_fields = _PVE_PLAYER_FIELDS if mode == "PVE" else _PVP_PLAYER_FIELDS
target_fields = _PVE_TARGET_FIELDS if mode == "PVE" else _PVP_TARGET_FIELDS
groups = _PVE_GROUPS if mode == "PVE" else _PVP_GROUPS

player_vals: dict = {}
target_vals: dict = {}

for grp_label, p_keys, t_keys in groups:
    summary = _group_summary(p_keys, t_keys, player_fields, target_fields, mode)
    with st.expander(f"**{grp_label}**  ·  {summary}"):
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Player**")
            for field in p_keys:
                label, default = player_fields[field]
                player_vals[field] = _render_input(
                    field, label, default, _field_key(f"dm_p_{mode}", field)
                )
        with col_b:
            if t_keys:
                st.markdown("**Target**")
            for field in t_keys:
                label, default = target_fields[field]
                target_vals[field] = _render_input(
                    field, label, default, _field_key(f"dm_t_{mode}", field)
                )

if st.button("Calculate", key="dm_btn"):
    p_dec = _pct_to_decimal(player_vals)
    t_dec = _pct_to_decimal(target_vals)
    if mode == "PVE":
        player = PVEPlayerStats(**p_dec)
        target = PVETargetStats(**t_dec)
        multiplier = pve_calculate_multiplier(player, target)
        weights = pve_modifier_weights(player, target)
    else:
        player = PVPPlayerStats(**p_dec)
        target = PVPTargetStats(**t_dec)
        multiplier = pvp_calculate_multiplier(player, target)
        weights = pvp_modifier_weights(player, target)

    # Sympy derivatives are w.r.t. decimal values; scale PCT fields by 0.01 so
    # weights represent change-per-1-unit-of-user-input across all stat types.
    weights = {k: (v * 0.01 if k in _PCT_FIELDS else v) for k, v in weights.items()}

    labels_map = {field: label for field, (label, _) in player_fields.items()}
    positive_weights = {
        k: v for k, v in weights.items()
        if v > 0 and k not in _SELECT_FIELDS
    }

    # Persist results so reruns from the reference selectbox don't clear them.
    st.session_state["dm_results"] = {
        "multiplier":      multiplier,
        "weights":         weights,
        "labels_map":      labels_map,
        "positive_weights": positive_weights,
        "best_stat":       max(positive_weights, key=positive_weights.get),
    }
    # Reset reference stat so it defaults to the best stat on new calculations.
    st.session_state.pop("dm_ref", None)

if "dm_results" in st.session_state:
    res             = st.session_state["dm_results"]
    multiplier      = res["multiplier"]
    weights         = res["weights"]
    labels_map      = res["labels_map"]
    positive_weights = res["positive_weights"]
    best_stat       = res["best_stat"]

    st.metric("Damage Multiplier", f"{multiplier:,.2f}")

    col_priority, col_equiv = st.columns(2)

    with col_priority:
        st.markdown("#### Stat Priority")
        st.caption(
            "All stats normalized so the highest-priority stat = 1.0. "
            "A stat with value 0.2 means you need **5× as many points** of it to match 1 point of the top stat. "
            "Hover for raw values."
        )
        st.plotly_chart(_weight_chart(weights, labels_map), width="stretch")

    with col_equiv:
        st.markdown("#### Stat Equivalence")
        st.caption("Select a reference stat to see how many points of every other stat equal 1 point of it.")
        ref_options = list(positive_weights.keys())
        current_ref = st.session_state.get("dm_ref", best_stat)
        if current_ref not in ref_options:
            current_ref = best_stat
        reference = st.selectbox(
            "Reference stat", options=ref_options,
            format_func=lambda k: labels_map[k],
            index=ref_options.index(current_ref),
            key="dm_ref",
        )
        _render_equivalence(positive_weights, labels_map, reference)
