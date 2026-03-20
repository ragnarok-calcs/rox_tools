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

import hashlib
import json
import uuid
import streamlit as st

from db import load_builds_for_user, save_builds_for_user, fetch_builds_by_ids

# ---------------------------------------------------------------------------
# Security / validation constants
# ---------------------------------------------------------------------------
_MAX_NAME_LEN = 64   # characters
_MAX_BUILDS   = 50   # per user
_MAX_UUID_IMPORT = 50  # UUIDs accepted in a single import_builds_by_uuid call

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
    'aspd':                 ('ASPD %',                        0),
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
    'total_final_pen', 'pdmg_bonus_pct',
    'crit_dmg_reduc', 'final_pdmg_reduc', 'element_resist', 'size_reduc',
    'race_reduc', 'final_dmg_reduc', 'pvp_final_pdmg_reduc',
    'total_final_def',
}

# Flat (non-pct) integer fields
INT_FIELDS = {'patk', 'aspd', 'pdmg_bonus', 'pdmg_bonus_pct', 'pdmg_reduc', 'pvp_pdmg_bonus', 'pvp_pdmg_reduc'}

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

# Scenario-level selectbox fields (not stored in build; set per-calculation in calculator pages)
SCENARIO_SELECT_FIELDS = {
    'weapon_size_modifier': [75, 100],
    'elemental_counter':    [0, 25, 50, 70, 75, 90, 100, 125, 150, 175],
}

# Grouped layout for the editor: (header, icon, [off_fields], [def_fields], effective_fn_pve, effective_fn_pvp)
# effective_fn(off_vals_raw, def_vals_raw) -> float
EDITOR_GROUPS = [
    ('Base Attack',  '⚔️',  ['patk', 'aspd', 'pdmg_bonus', 'pdmg_bonus_pct'],        ['pdmg_reduc'],               None, None),
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
        "weapon_type":           "one-handed",
        "weapon_enchant_lvl":    0,
        "armor_enchant_lvl":     0,
        "accessory_enchant_lvl": 0,
        "enchant_awakening":     0,
        "main_enchants":         [None, None, None],
        "sub_enchants":          [None, None, None],
        "drake_card":            False,
    }


# ---------------------------------------------------------------------------
# Validation / sanitization helpers
# ---------------------------------------------------------------------------
def _validate_build_name(name: str) -> str | None:
    """Return an error string if the name is invalid, else None."""
    name = name.strip()
    if not name:
        return "Build name cannot be empty."
    if len(name) > _MAX_NAME_LEN:
        return f"Build name must be {_MAX_NAME_LEN} characters or fewer (got {len(name)})."
    if name.startswith("$"):
        return "Build name cannot start with '$'."
    if "." in name:
        return "Build name cannot contain '.'."
    return None


def _sanitize_weapon_meta(raw: dict) -> dict:
    """Return a weapon_meta copy containing only known keys (whitelist filter)."""
    defaults = _wm_defaults()
    return {k: raw.get(k, defaults[k]) for k in defaults}


def _sanitize_canonical_name(name: str) -> str:
    """
    Sanitize a canonical_name sourced from the DB (written by a third party)
    so it is safe to use as a local build name / widget key.
    Never raises — always returns a non-empty string.
    """
    name = (name or "").strip()
    name = name.lstrip("$")          # strip leading $ operators
    name = name.replace(".", "_")    # dots are problematic as MongoDB field keys
    name = name[:_MAX_NAME_LEN]
    return name or "Imported Build"


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def _current_user_email() -> str | None:
    """
    Return the authenticated user's email, or None if not logged in.
    Local dev bypass: if no [auth] section exists in secrets, returns
    'dev@localhost' so the DB path works without real OAuth.
    Uses st.user (Streamlit 1.41+); is_logged_in is only present when
    auth is configured.
    """
    if not st.secrets.get("auth"):
        return "dev@localhost"
    try:
        if not st.user.is_logged_in:
            return None
        return st.user.get("email")
    except Exception:
        return None


def _user_key() -> str | None:
    """
    Return a one-way SHA-256 hash of the user's email for use as the DB key.
    The raw email is never stored in MongoDB — only this hash is used there.
    The same email always produces the same hash, so lookups remain consistent.
    """
    email = _current_user_email()
    if email is None:
        return None
    return hashlib.sha256(email.lower().encode()).hexdigest()


def _sync_to_db() -> None:
    """Write the current session builds to MongoDB. Silently toasts on failure."""
    key = _user_key()
    if key:
        try:
            save_builds_for_user(key, st.session_state["builds"])
        except Exception as e:
            st.toast(f"⚠️ DB sync failed: {e}")


# ---------------------------------------------------------------------------
# Session-state store helpers
# ---------------------------------------------------------------------------
def init_store():
    """
    Initialise the builds store.
    On the first call per session, ensures DB indexes exist then loads builds
    from MongoDB for the logged-in user. Subsequent calls are no-ops.
    """
    if "builds" in st.session_state:
        return
    from db import ensure_indexes
    try:
        ensure_indexes()
    except Exception:
        pass
    key = _user_key()
    if key:
        try:
            st.session_state["builds"] = load_builds_for_user(key)
        except Exception:
            st.session_state["builds"] = {}
    else:
        st.session_state["builds"] = {}


def get_builds() -> dict:
    init_store()
    return st.session_state["builds"]


def save_build(name: str, offensive: dict, defensive: dict, weapon_meta: dict | None = None):
    init_store()
    err = _validate_build_name(name)
    if err:
        raise ValueError(err)
    existing = st.session_state["builds"].get(name, {})
    if name not in st.session_state["builds"] and len(st.session_state["builds"]) >= _MAX_BUILDS:
        raise ValueError(f"Build limit ({_MAX_BUILDS}) reached — delete a build before saving a new one.")
    entry: dict = {
        "build_id":  existing.get("build_id") or str(uuid.uuid4()),
        "offensive": dict(offensive),
        "defensive": dict(defensive),
    }
    if weapon_meta is not None:
        entry["weapon_meta"] = dict(weapon_meta)
    st.session_state["builds"][name] = entry
    _sync_to_db()


def delete_build(name: str):
    init_store()
    st.session_state["builds"].pop(name, None)
    _sync_to_db()


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
        "weapon_type":           stored.get("weapon_type",           d["weapon_type"]),
        "weapon_enchant_lvl":    stored.get("weapon_enchant_lvl",    d["weapon_enchant_lvl"]),
        "armor_enchant_lvl":     stored.get("armor_enchant_lvl",     d["armor_enchant_lvl"]),
        "accessory_enchant_lvl": stored.get("accessory_enchant_lvl", d["accessory_enchant_lvl"]),
        "enchant_awakening":     stored.get("enchant_awakening",     d["enchant_awakening"]),
        "main_enchants":         stored.get("main_enchants",         d["main_enchants"]),
        "sub_enchants":          stored.get("sub_enchants",          d["sub_enchants"]),
        "drake_card":            stored.get("drake_card",            d["drake_card"]),
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
            err = _validate_build_name(name)
            if err:
                return 0, f"Invalid build name {name!r}: {err}"
            if len(st.session_state["builds"]) >= _MAX_BUILDS:
                return n, f"Build limit ({_MAX_BUILDS}) reached — import stopped."
            off = b.get("offensive", b.get("stats", {}))
            defn = b.get("defensive", {})
            entry = {
                "offensive": {f: off.get(f, default) for f, (_, default) in OFFENSIVE_FIELDS.items()},
                "defensive": {f: defn.get(f, default) for f, (_, default) in DEFENSIVE_FIELDS.items()},
            }
            if "weapon_meta" in b:
                entry["weapon_meta"] = _sanitize_weapon_meta(b["weapon_meta"])
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
    _sync_to_db()
    return n, None


def import_builds_by_uuid(raw_input: str) -> tuple[int, list]:
    """
    Parse one UUID per line from raw_input, fetch from the global builds
    collection, and merge into session state.
    Returns (n_imported, list_of_error_strings).
    """
    init_store()
    lines = [l.strip() for l in raw_input.splitlines() if l.strip()]
    if len(lines) > _MAX_UUID_IMPORT:
        return 0, [f"Too many UUIDs — limit is {_MAX_UUID_IMPORT} per import."]
    errors: list = []
    valid_ids: list = []
    for line in lines:
        try:
            uuid.UUID(line)
            valid_ids.append(line)
        except ValueError:
            errors.append(f"Invalid UUID: {line!r}")

    if not valid_ids:
        return 0, errors or ["No UUIDs entered."]

    fetched = fetch_builds_by_ids(valid_ids)
    for bid in valid_ids:
        if bid not in fetched:
            errors.append(f"Build not found: {bid}")

    n = 0
    existing_names = set(st.session_state["builds"])
    for bid, doc in fetched.items():
        if len(st.session_state["builds"]) >= _MAX_BUILDS:
            errors.append(f"Build limit ({_MAX_BUILDS}) reached — import stopped.")
            break
        base = _sanitize_canonical_name(doc.get("canonical_name", bid[:8]))
        name, i = base, 2
        while name in existing_names:
            name = f"{base} ({i})"
            i += 1
        off = doc.get("offensive", {})
        defn = doc.get("defensive", {})
        st.session_state["builds"][name] = {
            "build_id":    bid,
            "offensive":   {f: off.get(f, default)  for f, (_, default) in OFFENSIVE_FIELDS.items()},
            "defensive":   {f: defn.get(f, default) for f, (_, default) in DEFENSIVE_FIELDS.items()},
            "weapon_meta": doc.get("weapon_meta", _wm_defaults()),
        }
        existing_names.add(name)
        n += 1

    if n:
        _sync_to_db()
    return n, errors


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
    Pages call this once; it handles auth gate, upload / export / list.
    """
    # ── Auth gate ─────────────────────────────────────────────────────────
    email = _current_user_email()
    if email is None:
        with st.sidebar:
            if st.button("Log in with Google", key="sb_login", use_container_width=True):
                st.login("google")
        st.title("Ragnarok X Tools")
        st.info("Please log in to access your builds.")
        st.stop()

    init_store()
    if not st.secrets.get("auth"):
        st.warning(
            "⚠️ **Dev bypass active** — no `[auth]` section found in secrets. "
            "All users share the same `dev@localhost` account. "
            "Configure `[auth]` in `.streamlit/secrets.toml` before deploying.",
            icon="🔓",
        )
    with st.sidebar:
        try:
            display_email = st.user.get("email") if st.secrets.get("auth") else "dev@localhost"
        except Exception:
            display_email = email  # fall back to what _current_user_email() already resolved
        st.caption(f"👤 {display_email}")
        if st.secrets.get("auth") and st.button("Log out", key="sb_logout", use_container_width=True, type="tertiary"):
            st.session_state.pop("builds", None)
            st.logout()

        st.sidebar.page_link("app.py", label="Home", icon="🏠")
        st.divider()
        st.sidebar.markdown("**🔧 Tools**")
        st.sidebar.page_link("pages/Enchant_Lookup.py", label="Enchant Lookup")

        st.divider()
        st.sidebar.markdown("**⚔️ Build Testing**")
        st.sidebar.page_link("pages/Build_Editor.py", label="Build Editor")
        #st.sidebar.page_link("pages/Rotation_Builder.py", label="Rotation Builder")
        st.sidebar.page_link("pages/DMG_Calculator.py", label=" ⤷ Damage Calculator")
        st.sidebar.page_link("pages/Stat_Optimizer.py", label=" ⤷ Stat Optimizer")
        st.sidebar.page_link("pages/Enchant_Optimizer.py", label=" ⤷ Enchant Optimizer")
        #Sst.sidebar.page_link("pages/DPS_Simulator.py", label=" ⤷ DPS Simulator")

        st.divider()
        st.header("Builds")

        # ── Compact styling for build list rows ───────────────────────────
        st.markdown(
            """<style>
            /* Build name buttons: compact secondary style */
            section[data-testid="stSidebar"] button[kind="secondary"] {
                padding-top: 0.2rem !important;
                padding-bottom: 0.2rem !important;
                min-height: 1.75rem !important;
                font-size: 0.85rem !important;
            }
            /* Icon buttons (copy / delete): minimal, no extra space */
            section[data-testid="stSidebar"] button[kind="tertiary"] {
                padding-top: 0.15rem !important;
                padding-bottom: 0.15rem !important;
                min-height: 1.6rem !important;
            }
            </style>""",
            unsafe_allow_html=True,
        )

        # ── Import by ID (popover) ─────────────────────────────────────────
        with st.popover("⬇ Import Build", use_container_width=True):
            st.caption("Paste one or more build IDs, one per line:")
            uuid_input = st.text_area(
                "Build IDs", key="bs_uuid_input",
                label_visibility="collapsed", height=100,
                placeholder="e.g. 3f2a1b4c-…",
            )
            if st.button("Import", use_container_width=True, key="bs_import_uuid", type="primary"):
                if uuid_input.strip():
                    n, errors = import_builds_by_uuid(uuid_input)
                    for e in errors:
                        st.toast(e, icon="❌")
                    if n:
                        st.toast(f"Imported {n} build(s).", icon="✅")
                        st.rerun()
                else:
                    st.toast("Paste at least one build ID.", icon="⚠️")

        st.divider()

        # ── Build list ────────────────────────────────────────────────────
        builds = get_builds()
        if builds:
            for bname in list(builds.keys()):
                # Use build_id (UUID fragment) as widget key — safe regardless of build name content
                _bid = builds[bname].get("build_id", "")
                _ksuf = _bid[:8] if _bid else str(abs(hash(bname)) % 10**8)
                col_name, col_copy, col_del = st.columns([6, 1, 1], vertical_alignment="center")
                with col_name:
                    if st.button(bname, key=f"bs_nav_{_ksuf}", use_container_width=True,
                                 type="secondary", help="Open in Build Editor"):
                        st.session_state["bs_editing"] = bname
                        st.switch_page("pages/Build_Editor.py")
                with col_copy:
                    if st.button(" ", key=f"bs_copy_{_ksuf}", type="tertiary",
                                 icon=":material/content_copy:",
                                 help="Copy build ID to clipboard"):
                        st.session_state["_bs_copy_id"] = builds[bname].get("build_id", "")
                with col_del:
                    if st.button(" ", key=f"bs_del_{_ksuf}", type="tertiary",
                                 icon=":material/delete:",
                                 help=f"Delete {bname}"):
                        delete_build(bname)
                        st.rerun()

            # ── Bottom action row ─────────────────────────────────────────
            col_new, col_copy_all = st.columns([9, 1])
            with col_new:
                if st.button("＋ New Build", use_container_width=True, key="bs_new"):
                    st.session_state.pop("bs_editing", None)
                    st.session_state["be_selected"] = "— New Build —"
                    st.session_state.pop("_be_prev_sel", None)
                    st.switch_page("pages/Build_Editor.py")
            with col_copy_all:
                if st.button(" ", key="bs_copy_all", type="tertiary",
                             icon=":material/content_copy:",
                             help="Copy all build IDs to clipboard"):
                    all_ids = "\n".join(
                        b.get("build_id", "") for b in builds.values() if b.get("build_id")
                    )
                    st.session_state["_bs_copy_id"] = all_ids

            # ── Clipboard copy ────────────────────────────────────────────
            # Placed after ALL buttons that can set _bs_copy_id so that
            # both single-copy and copy-all resolve in one rerun.
            # Always rendered (height=0) so the iframe is a stable DOM
            # node and the New Build button never shifts position.
            # A millisecond nonce makes the HTML unique each time there is
            # content to copy, forcing Streamlit to re-execute the script
            # even for repeated copies of the same build.
            import json as _json
            import time as _time
            import streamlit.components.v1 as _stc
            _copy_val = st.session_state.pop("_bs_copy_id", None)
            _copy_js  = _json.dumps(_copy_val or "")
            _is_all   = bool(_copy_val and "\n" in _copy_val)
            _nonce    = int(_time.time() * 1000) if _copy_val else 0
            _stc.html(
                f"""<script>
                /* {_nonce} */
                (async () => {{
                    var text = {_copy_js};
                    if (!text) return;
                    try {{
                        await window.parent.navigator.clipboard.writeText(text);
                    }} catch (_) {{
                        var inp = window.parent.document.createElement("textarea");
                        inp.value = text;
                        inp.style.cssText = "position:fixed;opacity:0";
                        window.parent.document.body.appendChild(inp);
                        inp.focus(); inp.select();
                        window.parent.document.execCommand("copy");
                        window.parent.document.body.removeChild(inp);
                    }}
                }})();
                </script>""",
                height=0,
            )
            if _copy_val:
                if _is_all:
                    st.toast(f"All {len(builds)} build IDs copied!", icon=":material/content_copy:")
                else:
                    st.toast("Build ID copied to clipboard!", icon=":material/content_copy:")
        else:
            st.caption("No builds saved yet.")

