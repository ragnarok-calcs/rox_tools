"""
build_store.py
--------------
Shared field definitions, session-state helpers, and calculation dispatch
used by Build_Editor, DMG_Calculator, and Stat_Optimization pages.

Unified build schema stored in st.session_state["builds"]:
    {
        "Build Name": {
            "offensive": { field: value, ... },
            "defensive": { field: value, ... },
        }
    }
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

import json
import streamlit as st

from multiplier_stats import (
    PVEPlayerStats, PVETargetStats, pve_calculate_multiplier, pve_modifier_weights,
    PVPPlayerStats, PVPTargetStats, pvp_calculate_multiplier, pvp_modifier_weights,
    pen_multiplier,
)

# ---------------------------------------------------------------------------
# Field definitions: {field: (label, default)}
# ---------------------------------------------------------------------------
OFFENSIVE_FIELDS = {
    'patk':                 ('P/MATK',                        1000),
    'crit_dmg_bonus':       ('Crit DMG Bonus %',               200),
    'pdmg_bonus':           ('P.DMG/M.DMG Bonus',              0),
    'pdmg_bonus_pct':       ('P.DMG/M.DMG Bonus %',            0),
    'final_pdmg_bonus':     ('Final P.DMG/M.DMG Bonus %',      0),
    'weapon_size_modifier': ('Weapon Size Modifier %',          100),
    'size_enhance':         ('Bonus DMG to Size %',             0),
    'elemental_counter':    ('Elemental Counter %',             100),
    'element_enhance':      ('Element Enhance %',               0),
    'bonus_dmg_element':    ('Bonus DMG to Element %',          0),
    'bonus_dmg_race':       ('Bonus DMG to Race %',             0),
    'final_dmg_bonus':      ('Final DMG Bonus %',               0),
    'pvp_final_pdmg_bonus': ('PVP Final P.DMG/M.DMG Bonus %',  0),
    'pvp_pdmg_bonus':       ('PVP P.DMG/M.DMG Bonus',          0),
    'total_final_pen':      ('Total Final PEN %',               0),
}

DEFENSIVE_FIELDS = {
    'crit_dmg_reduc':       ('Crit DMG Reduction %',              0),
    'pdmg_reduc':           ('P.DMG/M.DMG Reduction',             0),
    'final_pdmg_reduc':     ('Final P.DMG/M.DMG Reduction %',     0),
    'element_resist':       ('Element Resist %',                   0),
    'size_reduc':           ('Size Reduction %',                   0),
    'race_reduc':           ('Race Reduction %',                   0),
    'final_dmg_reduc':      ('Final DMG Reduction %',              0),
    'pvp_pdmg_reduc':       ('PVP P.DMG/M.DMG Reduction',         0),
    'pvp_final_pdmg_reduc': ('PVP Final P.DMG/M.DMG Reduction %', 0),
    'total_final_def':      ('Total Final DEF %',                  0),
}

# Fields stored as integer percentages in UI (divided by 100 before formula use)
PCT_FIELDS = {
    'crit_dmg_bonus', 'final_pdmg_bonus', 'weapon_size_modifier', 'size_enhance',
    'elemental_counter', 'element_enhance', 'bonus_dmg_element',
    'bonus_dmg_race', 'final_dmg_bonus', 'pvp_final_pdmg_bonus',
    'total_final_pen',
    'crit_dmg_reduc', 'final_pdmg_reduc', 'element_resist', 'size_reduc',
    'race_reduc', 'final_dmg_reduc', 'pvp_final_pdmg_reduc',
    'total_final_def',
}

# Flat (non-pct) integer fields
INT_FIELDS = {'patk', 'pdmg_bonus', 'pdmg_bonus_pct', 'pdmg_reduc', 'pvp_pdmg_bonus', 'pvp_pdmg_reduc'}

# PCT fields that use float input (2 decimal places) instead of integer
FLOAT_PCT_FIELDS = {
    'total_final_pen', 'total_final_def',
    'final_pdmg_bonus', 'final_pdmg_reduc',
    'size_enhance', 'size_reduc',
    'element_enhance', 'bonus_dmg_element', 'element_resist',
    'bonus_dmg_race', 'race_reduc',
    'final_dmg_bonus', 'final_dmg_reduc',
    'pvp_final_pdmg_bonus', 'pvp_final_pdmg_reduc',
}

# Selectbox fields: {field: [option_ints]}
SELECT_FIELDS = {
    'weapon_size_modifier': [75, 100],
    'elemental_counter':    [0, 25, 50, 70, 75, 90, 100, 125, 150, 175],
}

# Grouped layout for the editor: (header, icon, [off_fields], [def_fields], effective_fn_pve, effective_fn_pvp)
# effective_fn(off_vals_raw, def_vals_raw) -> float
EDITOR_GROUPS = [
    ('Base Attack',  '⚔️',  ['patk', 'pdmg_bonus', 'pdmg_bonus_pct'],               ['pdmg_reduc'],               None, None),
    ('Crit',         '💥',  ['crit_dmg_bonus'],                                       ['crit_dmg_reduc'],
        lambda o, d: max(o['crit_dmg_bonus'] / 100 - d['crit_dmg_reduc'] / 100, 0.2),
        lambda o, d: max(o['crit_dmg_bonus'] / 100 - d['crit_dmg_reduc'] / 100, 0.2),
    ),
    ('Penetration',  '🔱',  ['total_final_pen'],                                      ['total_final_def'],
        lambda o, d: pen_multiplier((o['total_final_pen'] - d['total_final_def']) / 100),
        lambda o, d: pen_multiplier((o['total_final_pen'] - d['total_final_def']) / 100),
    ),
    ('Final P/M.DMG','🎯',  ['final_pdmg_bonus'],                                     ['final_pdmg_reduc'],
        lambda o, d: max(1 + (o['final_pdmg_bonus'] - d['final_pdmg_reduc']) / 100, 0.2),
        lambda o, d: max(1 + (o['final_pdmg_bonus'] - d['final_pdmg_reduc']) / 100, 0.2),
    ),
    ('Size',         '📏',  ['weapon_size_modifier', 'size_enhance'],                 ['size_reduc'],
        lambda o, d: max((o['weapon_size_modifier'] + o['size_enhance']) / 100, 0.2),
        lambda o, d: max((o['weapon_size_modifier'] + o['size_enhance'] - d['size_reduc']) / 100, 0.2),
    ),
    ('Element',      '🌀',  ['elemental_counter', 'element_enhance'],                   ['element_resist'],
        lambda o, d: max((o['elemental_counter'] + o['element_enhance']) / 100, 0.2),
        lambda o, d: max((o['elemental_counter'] + o['element_enhance'] - d['element_resist']) / 100, 0.2),
    ),
    ('Monster Elem', '🎯',  ['bonus_dmg_element'],                                      [],
        lambda o, d: 1 + o['bonus_dmg_element'] / 100,
        None,
    ),
    ('Race',         '👥',  ['bonus_dmg_race'],                                       ['race_reduc'],
        lambda o, d: 1 + o['bonus_dmg_race'] / 100,
        lambda o, d: max(1 + (o['bonus_dmg_race'] - d['race_reduc']) / 100, 0.2),
    ),
    ('Final DMG',    '🔥',  ['final_dmg_bonus'],                                      ['final_dmg_reduc'],
        lambda o, d: max(1 + (o['final_dmg_bonus'] - d['final_dmg_reduc']) / 100, 0.2),
        lambda o, d: max(1 + (o['final_dmg_bonus'] - d['final_dmg_reduc']) / 100, 0.2),
    ),
    ('PVP DMG',      '⚡',  ['pvp_final_pdmg_bonus', 'pvp_pdmg_bonus'],               ['pvp_pdmg_reduc', 'pvp_final_pdmg_reduc'],
        None,
        lambda o, d: max(1 + (o['pvp_final_pdmg_bonus'] - d['pvp_final_pdmg_reduc']) / 100, 0.2),
    ),
]


# ---------------------------------------------------------------------------
# Default build values
# ---------------------------------------------------------------------------
def _off_defaults() -> dict:
    return {f: default for f, (_, default) in OFFENSIVE_FIELDS.items()}

def _def_defaults() -> dict:
    return {f: default for f, (_, default) in DEFENSIVE_FIELDS.items()}

def _wm_defaults() -> dict:
    return {
        "weapon_type":      "one-handed",
        "enchant_awakening": 0,
        "main_enchants":    [None, None, None],
        "sub_enchants":     [None, None, None],
        "drake_card":       False,
    }


# ---------------------------------------------------------------------------
# Session-state store helpers
# ---------------------------------------------------------------------------
def init_store():
    """Initialise the builds store if not already present."""
    if "builds" not in st.session_state:
        st.session_state["builds"] = {}


def get_builds() -> dict:
    init_store()
    return st.session_state["builds"]


def save_build(name: str, offensive: dict, defensive: dict, weapon_meta: dict | None = None):
    init_store()
    entry: dict = {
        "offensive": dict(offensive),
        "defensive": dict(defensive),
    }
    if weapon_meta is not None:
        entry["weapon_meta"] = dict(weapon_meta)
    st.session_state["builds"][name] = entry


def delete_build(name: str):
    init_store()
    st.session_state["builds"].pop(name, None)


def get_build_offensive(name: str) -> dict:
    builds = get_builds()
    if name not in builds:
        return _off_defaults()
    raw = builds[name].get("offensive", {})
    return {f: raw.get(f, default) for f, (_, default) in OFFENSIVE_FIELDS.items()}


def get_build_defensive(name: str) -> dict:
    builds = get_builds()
    if name not in builds:
        return _def_defaults()
    raw = builds[name].get("defensive", {})
    return {f: raw.get(f, default) for f, (_, default) in DEFENSIVE_FIELDS.items()}


def get_build_weapon_meta(name: str) -> dict:
    builds = get_builds()
    if name not in builds:
        return _wm_defaults()
    stored = builds[name].get("weapon_meta", {})
    d = _wm_defaults()
    return {
        "weapon_type":       stored.get("weapon_type",       d["weapon_type"]),
        "enchant_awakening": stored.get("enchant_awakening", d["enchant_awakening"]),
        "main_enchants":     stored.get("main_enchants",     d["main_enchants"]),
        "sub_enchants":      stored.get("sub_enchants",      d["sub_enchants"]),
        "drake_card":        stored.get("drake_card",        d["drake_card"]),
    }


# ---------------------------------------------------------------------------
# Import / Export
# ---------------------------------------------------------------------------
def export_builds_json() -> str:
    """Serialise the current builds store to JSON."""
    return json.dumps({"builds": get_builds()}, indent=2)


def import_builds_data(data: dict):
    """
    Merge imported data into the session builds store.
    Accepts the new unified schema {"builds": {...}} as well as the legacy
    {"player_builds": {...}, "target_builds": {...}} format.
    Returns (n_imported, error_message_or_None).
    """
    init_store()
    n = 0
    if "builds" in data:
        for name, b in data["builds"].items():
            off = b.get("offensive", b.get("stats", {}))
            defn = b.get("defensive", {})
            entry = {
                "offensive": {f: off.get(f, default) for f, (_, default) in OFFENSIVE_FIELDS.items()},
                "defensive": {f: defn.get(f, default) for f, (_, default) in DEFENSIVE_FIELDS.items()},
            }
            if "weapon_meta" in b:
                entry["weapon_meta"] = b["weapon_meta"]
            st.session_state["builds"][name] = entry
            n += 1
    elif "player_builds" in data or "target_builds" in data:
        # Legacy: merge player stats → offensive, target stats → defensive, keyed by shared names
        for name, b in data.get("player_builds", {}).items():
            raw = b.get("stats", b)
            existing_def = get_build_defensive(name)
            st.session_state["builds"][name] = {
                "offensive": {f: raw.get(f, default) for f, (_, default) in OFFENSIVE_FIELDS.items()},
                "defensive": existing_def,
            }
            n += 1
        for name, b in data.get("target_builds", {}).items():
            raw = b.get("stats", b)
            existing_off = get_build_offensive(name)
            st.session_state["builds"].setdefault(name, {"offensive": existing_off, "defensive": {}})
            st.session_state["builds"][name]["defensive"] = {
                f: raw.get(f, default) for f, (_, default) in DEFENSIVE_FIELDS.items()
            }
            n += 1
    else:
        return 0, "Unrecognised file format."
    return n, None


# ---------------------------------------------------------------------------
# Calculation helpers
# ---------------------------------------------------------------------------
def pct_to_decimal(vals: dict) -> dict:
    return {k: v / 100.0 if k in PCT_FIELDS else v for k, v in vals.items()}


def apply_card_effects(off_raw: dict, def_raw: dict, weapon_meta: dict) -> tuple[dict, dict]:
    """Return (off_raw, def_raw) copies with card effects applied.

    Drake Card: makes the entire size multiplier exactly ×1.0 by zeroing
    weapon_size_modifier to 100, size_enhance to 0, and size_reduc to 0.
    This neutralises both the offensive size penalty and any defensive size
    reduction, which is the correct in-game behaviour.
    """
    if not weapon_meta.get("drake_card", False):
        return off_raw, def_raw
    off_result = dict(off_raw)
    def_result = dict(def_raw)
    off_result["weapon_size_modifier"] = 100
    off_result["size_enhance"] = 0
    def_result["size_reduc"] = 0
    return off_result, def_result


def _off_for_mode(off_dec: dict, mode: str) -> dict:
    """Extract the subset of offensive decimal values for a given mode's PlayerStats."""
    if mode == "PVE":
        return {f: off_dec[f] for f in PVEPlayerStats.__dataclass_fields__}
    return {f: off_dec[f] for f in PVPPlayerStats.__dataclass_fields__}


def _def_for_mode(def_dec: dict, mode: str) -> dict:
    """Extract the subset of defensive decimal values for a given mode's TargetStats."""
    if mode == "PVE":
        return {f: def_dec[f] for f in PVETargetStats.__dataclass_fields__}
    return {f: def_dec[f] for f in PVPTargetStats.__dataclass_fields__}


def calculate(mode: str, off_raw: dict, def_raw: dict,
              dmg_type: str = "crit", attack_mult: int = 8) -> float:
    """Calculate damage multiplier. off_raw / def_raw are raw UI (integer %) values."""
    off_dec = pct_to_decimal(off_raw)
    def_dec = pct_to_decimal(def_raw)
    if mode == "PVE":
        return pve_calculate_multiplier(
            PVEPlayerStats(**_off_for_mode(off_dec, "PVE")),
            PVETargetStats(**_def_for_mode(def_dec, "PVE")),
            dmg_type, attack_mult,
        )
    return pvp_calculate_multiplier(
        PVPPlayerStats(**_off_for_mode(off_dec, "PVP")),
        PVPTargetStats(**_def_for_mode(def_dec, "PVP")),
        dmg_type, attack_mult,
    )


def get_weights(mode: str, off_raw: dict, def_raw: dict,
                dmg_type: str = "crit", attack_mult: int = 8,
                hybrid_crit_pct: float = 0.5) -> dict[str, float]:
    """Return marginal weights for offensive stats (raw % units).

    dmg_type "hybrid": weights are a weighted combination of crit and pen weights.
    Since D_hybrid = crit_pct×D_crit + pen_pct×D_pen, its derivative is the same
    linear combination: w_hybrid = crit_pct×w_crit + pen_pct×w_pen.
    """
    if dmg_type == "hybrid":
        pen_pct = 1.0 - hybrid_crit_pct
        w_crit = get_weights(mode, off_raw, def_raw, "crit", attack_mult)
        w_pen  = get_weights(mode, off_raw, def_raw, "pen",  attack_mult)
        return {k: hybrid_crit_pct * w_crit.get(k, 0.0) + pen_pct * w_pen.get(k, 0.0)
                for k in set(w_crit) | set(w_pen)}

    off_dec = pct_to_decimal(off_raw)
    def_dec = pct_to_decimal(def_raw)
    if mode == "PVE":
        raw_w = pve_modifier_weights(
            PVEPlayerStats(**_off_for_mode(off_dec, "PVE")),
            PVETargetStats(**_def_for_mode(def_dec, "PVE")),
            dmg_type, attack_mult,
        )
    else:
        raw_w = pvp_modifier_weights(
            PVPPlayerStats(**_off_for_mode(off_dec, "PVP")),
            PVPTargetStats(**_def_for_mode(def_dec, "PVP")),
            dmg_type, attack_mult,
        )
    # Scale pct fields so weight = Δmultiplier per 1 percentage point of UI input
    return {k: (v * 0.01 if k in PCT_FIELDS else v) for k, v in raw_w.items()}


# ---------------------------------------------------------------------------
# Sidebar build manager (shared across pages)
# ---------------------------------------------------------------------------
def render_sidebar():
    """
    Render the shared build manager in the sidebar.
    Pages call this once; it handles upload / export / list.
    """
    init_store()
    with st.sidebar:
        st.sidebar.page_link("app.py", label="Home", icon="🏠")
        st.divider()
        st.sidebar.markdown("**🔧 Tools**")
        st.sidebar.page_link("pages/Enchant_Lookup.py", label="Enchant Lookup")
        st.sidebar.page_link("pages/Enchant_Optimizer.py", label="Enchant Optimizer")
        st.divider()
        st.sidebar.markdown("**⚔️ Build Testing**")
        st.sidebar.page_link("pages/Build_Editor.py", label="Build Editor")
        st.sidebar.page_link("pages/DMG_Calculator.py", label=" ⤷ Damage Calculator")
        st.sidebar.page_link("pages/Stat_Optimizer.py", label=" ⤷ Stat Optimizer")

        st.divider()
        st.header("Upload/Download Builds")
        # ── File uploader (hidden once a file has been loaded) ────────────
        if not st.session_state.get("_bs_file_loaded"):
            uploaded_files = st.file_uploader(
                "Load builds from JSON", type=["json"],
                key="bs_uploader", accept_multiple_files=True,
            )
            if uploaded_files:
                last_name = ""
                for uf in uploaded_files:
                    file_id = f"_bs_loaded_{id(uf)}_{uf.name}"
                    if st.session_state.get(file_id):
                        continue
                    st.session_state[file_id] = True
                    try:
                        data = json.load(uf)
                        n, err = import_builds_data(data)
                        if err:
                            st.toast(f"{uf.name}: {err}", icon="❌")
                        else:
                            st.toast(f"{uf.name}: loaded {n} build(s).", icon="✅")
                            last_name = uf.name
                    except Exception as e:
                        st.toast(f"{uf.name}: {e}", icon="❌")
                if last_name:
                    st.session_state["_bs_file_loaded"] = True
                    st.session_state["_bs_loaded_filename"] = last_name
                    st.rerun()
        else:
            loaded_name = st.session_state.get("_bs_loaded_filename", "builds")
            col_fn, col_clr = st.columns([5, 2], vertical_alignment="center")
            with col_fn:
                st.caption(f"📄 {loaded_name}")
            with col_clr:
                if st.button(":red[✕]", key="bs_clear_file", width="content", type="tertiary",
                             help="Remove the loaded file and clear all builds"):
                    for key in list(st.session_state.keys()):
                        if key.startswith("_bs_loaded_") or key in ("_bs_file_loaded", "bs_uploader"):
                            st.session_state.pop(key, None)
                    st.session_state["builds"] = {}
                    st.rerun()

        builds = get_builds()
        if builds:
            st.download_button(
                f"⬇ Export builds ({len(builds)})",
                data=export_builds_json(),
                file_name="rag_builds.json",
                mime="application/json",
                use_container_width=True,
                key="bs_download",
            )

        st.divider()

        # ── Build list ────────────────────────────────────────────────────
        if builds:
            for bname in list(builds.keys()):
                col_n, col_edit, col_del = st.columns([5, 1, 1], vertical_alignment="center")
                with col_n:
                    st.markdown(bname)
                with col_edit:
                    if st.button("✏️", key=f"bs_edit_{bname}", help=f"Edit {bname}",
                                 width="content", type="tertiary"):
                        st.session_state["bs_editing"] = bname
                        st.switch_page("pages/Build_Editor.py")
                with col_del:
                    if st.button("🗑️", key=f"bs_del_{bname}", width="content", type="tertiary"):
                        delete_build(bname)
                        st.rerun()
            if st.button("＋ New Build", use_container_width=True, key="bs_new"):
                st.session_state.pop("bs_editing", None)
                st.session_state["be_selected"] = "— New Build —"
                st.session_state.pop("_be_prev_sel", None)
                st.switch_page("pages/Build_Editor.py")

            if st.button("🗑 Clear all builds", use_container_width=True, key="bs_clear_all",
                         help="Delete all saved builds from this session"):
                st.session_state["builds"] = {}
                st.rerun()
        else:
            st.caption("No builds saved yet.")

