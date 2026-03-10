"""
Dev Tools — Gear DB Editor
---------------------------
CRUD interface for ragnarok_x/data/gear_db.json.
Not intended for end users.

Item structure per entry:
  {
    "exclusive": { stat: value, ... },   # fixed identity stats
    "base":      { stat: value, ... },   # primary scaling stats
    "upgrade":   [ {}, {stat: v}, ... ], # cumulative bonus at each upgrade level
    "refine":    [ {}, {stat: v}, ... ], # cumulative bonus at each refine level (+0..+15)
    "two_handed": true                   # optional, Weapon slot only
  }
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
from data import gear_db as _gear_db_module

st.set_page_config(page_title="Dev — Gear DB", layout="wide")
st.title("Dev Tools: Gear DB Editor")
st.caption(f"Editing `{_gear_db_module._JSON_PATH}`")

# ---------------------------------------------------------------------------
# Stat field metadata
# ---------------------------------------------------------------------------
STAT_FIELDS = [
    "patk", "crit_dmg_bonus", "pdmg_bonus", "pdmg_bonus_pct",
    "final_pdmg_bonus", "elemental_counter", "element_enhance",
    "bonus_dmg_element", "bonus_dmg_race", "final_dmg_bonus",
    "weapon_size_modifier", "size_enhance", "pvp_final_pdmg_bonus", "pvp_pdmg_bonus",
]

STAT_LABELS = {
    "patk":                 "P.ATK",
    "crit_dmg_bonus":       "Crit DMG Bonus %",
    "pdmg_bonus":           "P.DMG Bonus",
    "pdmg_bonus_pct":       "P.DMG Bonus %",
    "final_pdmg_bonus":     "Final P.DMG Bonus %",
    "elemental_counter":    "Elemental Counter %",
    "element_enhance":      "Element Enhance %",
    "bonus_dmg_element":    "Bonus DMG to Element %",
    "bonus_dmg_race":       "Bonus DMG to Race %",
    "final_dmg_bonus":      "Final DMG Bonus %",
    "weapon_size_modifier": "Weapon Size Modifier %",
    "size_enhance":         "Bonus DMG to Size %",
    "pvp_final_pdmg_bonus": "PVP Final P.DMG Bonus %",
    "pvp_pdmg_bonus":       "PVP P.DMG Bonus",
}

_INT_FIELDS = {"patk", "pdmg_bonus", "pvp_pdmg_bonus"}

SLOTS = [
    "Weapon", "Off-Hand", "Armor", "Cloak", "Shoes",
    "Accessory 1", "Accessory 2", "Talisman 1", "Talisman 2",
]

# ---------------------------------------------------------------------------
# Load / reload DB into session state
# ---------------------------------------------------------------------------
def _load_db():
    st.session_state["dev_gear_db"] = _gear_db_module.load()

if "dev_gear_db" not in st.session_state:
    _load_db()

def _save_db():
    _gear_db_module.save(st.session_state["dev_gear_db"])

db: dict = st.session_state["dev_gear_db"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _stat_input(label: str, field: str, value: int | float, key: str) -> int:
    help_txt = None if field in _INT_FIELDS else "Percentage units (e.g. 5 = 5%)"
    return st.number_input(label, value=int(value), min_value=0, step=1,
                           key=key, help=help_txt)

def _stat_section_inputs(section_stats: dict, key_prefix: str) -> dict:
    """Render a 3-column grid of stat inputs for a section dict."""
    cols = st.columns(3)
    out = {}
    for i, field in enumerate(STAT_FIELDS):
        with cols[i % 3]:
            out[field] = _stat_input(
                STAT_LABELS[field], field,
                section_stats.get(field, 0),
                key=f"{key_prefix}_{field}",
            )
    return out

def _stat_summary(stats: dict) -> str:
    parts = [f"{STAT_LABELS.get(k, k)}: {v:+g}"
             for k, v in stats.items() if k in STAT_FIELDS and v != 0]
    return "  |  ".join(parts) if parts else "—"

def _item_summary(item_data: dict) -> str:
    """One-line summary shown in the item list."""
    tags = []
    if item_data.get("two_handed"):
        tags.append("[2H]")
    excl = _stat_summary(item_data.get("exclusive", {}))
    base = _stat_summary(item_data.get("base", {}))
    if excl != "—":
        tags.append(f"Excl: {excl}")
    if base != "—":
        tags.append(f"Base: {base}")
    return "  |  ".join(tags) if tags else "—"

def _level_list_summary(levels: list[dict]) -> str:
    non_empty = [(i, d) for i, d in enumerate(levels) if d]
    if not non_empty:
        return "all zeros"
    return ",  ".join(f"Lv.{i}: {_stat_summary(d)}" for i, d in non_empty[:4])

# ---------------------------------------------------------------------------
# Slot selector
# ---------------------------------------------------------------------------
slot = st.selectbox("Gear Slot", SLOTS, key="dev_slot")
slot_items: dict = db.setdefault(slot, {})
slot_items.setdefault("None", {"exclusive": {}, "base": {}, "upgrade": [{}], "refine": [{}]})

st.divider()

# ---------------------------------------------------------------------------
# Item list (Read + Delete)
# ---------------------------------------------------------------------------
st.subheader(f"{slot} — Items ({len(slot_items)})")

for item_name, item_data in list(slot_items.items()):
    col_name, col_summary, col_edit, col_del = st.columns([2, 5, 1, 1])
    with col_name:
        st.markdown(f"**{item_name}**")
    with col_summary:
        st.caption(_item_summary(item_data))
    with col_edit:
        if item_name != "None":
            if st.button("Edit", key=f"edit_{slot}_{item_name}"):
                st.session_state["dev_edit_item"] = item_name
                st.session_state["dev_edit_slot"] = slot
                st.rerun()
    with col_del:
        if item_name != "None":
            if st.button("Delete", key=f"del_{slot}_{item_name}", type="primary"):
                del slot_items[item_name]
                _save_db()
                if st.session_state.get("dev_edit_item") == item_name:
                    st.session_state.pop("dev_edit_item", None)
                    st.session_state.pop("dev_edit_slot", None)
                st.toast(f"Deleted '{item_name}' from {slot}", icon="🗑️")
                st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Add / Edit form (Create + Update)
# ---------------------------------------------------------------------------
editing_item = st.session_state.get("dev_edit_item")
editing_slot = st.session_state.get("dev_edit_slot")

if editing_slot and editing_slot != slot:
    editing_item = None
    st.session_state.pop("dev_edit_item", None)
    st.session_state.pop("dev_edit_slot", None)

is_edit = editing_item is not None
existing: dict = slot_items.get(editing_item, {}) if is_edit else {}

st.subheader(f"Edit: {editing_item}" if is_edit else "Add New Item")

with st.form("item_form", clear_on_submit=not is_edit):
    item_name_input = st.text_input(
        "Item Name",
        value=editing_item if is_edit else "",
        placeholder="e.g. Mythic Sword +0 (Medium)",
    )

    tab_excl, tab_base, tab_upg, tab_ref = st.tabs(
        ["Exclusive", "Base", "Upgrade Levels", "Refine Levels"]
    )

    # ── Exclusive ────────────────────────────────────────────────────────
    with tab_excl:
        st.caption("Fixed stats that define the item's identity (e.g. Crit DMG +35%)")
        excl_vals = _stat_section_inputs(existing.get("exclusive", {}), "excl")

    # ── Base ─────────────────────────────────────────────────────────────
    with tab_base:
        st.caption("Primary scaling stats (P.ATK, Weapon Size Modifier)")
        base_vals = _stat_section_inputs(existing.get("base", {}), "base")

    # ── Upgrade levels ───────────────────────────────────────────────────
    with tab_upg:
        existing_upg: list[dict] = existing.get("upgrade", [{}])
        st.caption(
            f"Cumulative bonus at each upgrade level. "
            f"Current: {_level_list_summary(existing_upg)}"
        )
        n_upg = st.number_input(
            "Number of upgrade levels (including Lv.0)",
            min_value=1, max_value=10, step=1,
            value=len(existing_upg),
            key="form_n_upg",
        )
        upg_vals: list[dict] = []
        for li in range(int(n_upg)):
            st.markdown(f"**Upgrade Lv.{li}**")
            prev = existing_upg[li] if li < len(existing_upg) else {}
            lv_cols = st.columns(3)
            lv_stats = {}
            for fi, field in enumerate(STAT_FIELDS):
                with lv_cols[fi % 3]:
                    lv_stats[field] = _stat_input(
                        STAT_LABELS[field], field, prev.get(field, 0),
                        key=f"upg_{li}_{field}",
                    )
            upg_vals.append({f: v for f, v in lv_stats.items() if v != 0})

    # ── Refine levels ────────────────────────────────────────────────────
    with tab_ref:
        existing_ref: list[dict] = existing.get("refine", [{}])
        st.caption(
            f"Cumulative bonus at each refine level (+0 to +15). "
            f"Current: {_level_list_summary(existing_ref)}"
        )
        n_ref = st.number_input(
            "Number of refine levels (index 0 = +0, max 16 for +0..+15)",
            min_value=1, max_value=16, step=1,
            value=len(existing_ref),
            key="form_n_ref",
        )
        ref_vals: list[dict] = []
        for li in range(int(n_ref)):
            label = f"+{li}" if li > 0 else "+0 (no bonus)"
            st.markdown(f"**Refine {label}**")
            prev = existing_ref[li] if li < len(existing_ref) else {}
            lv_cols = st.columns(3)
            lv_stats = {}
            for fi, field in enumerate(STAT_FIELDS):
                with lv_cols[fi % 3]:
                    lv_stats[field] = _stat_input(
                        STAT_LABELS[field], field, prev.get(field, 0),
                        key=f"ref_{li}_{field}",
                    )
            ref_vals.append({f: v for f, v in lv_stats.items() if v != 0})

    # ── Two-handed checkbox (Weapon slot only) ────────────────────────────
    two_handed_val = False
    if slot == "Weapon":
        st.divider()
        two_handed_val = st.checkbox(
            "Two-handed weapon (locks Off-Hand slot)",
            value=bool(existing.get("two_handed", False)),
            key="form_two_handed",
        )

    col_submit, col_cancel = st.columns([1, 1])
    with col_submit:
        submitted = st.form_submit_button(
            "Update Item" if is_edit else "Add Item",
            type="primary", use_container_width=True,
        )
    with col_cancel:
        cancelled = st.form_submit_button(
            "Cancel", use_container_width=True, disabled=not is_edit,
        )

if cancelled:
    st.session_state.pop("dev_edit_item", None)
    st.session_state.pop("dev_edit_slot", None)
    st.rerun()

if submitted:
    name = item_name_input.strip()
    if not name:
        st.error("Item name cannot be empty.")
    elif name == "None":
        st.error('"None" is reserved.')
    elif not is_edit and name in slot_items:
        st.error(f"'{name}' already exists in {slot}. Use Edit to modify it.")
    else:
        new_item = {
            "exclusive": {f: v for f, v in excl_vals.items() if v != 0},
            "base":      {f: v for f, v in base_vals.items() if v != 0},
            "upgrade":   upg_vals,
            "refine":    ref_vals,
        }
        if slot == "Weapon" and two_handed_val:
            new_item["two_handed"] = True

        if is_edit and name != editing_item:
            # Rename: preserve position
            items_list = list(slot_items.items())
            old_idx = next(i for i, (k, _) in enumerate(items_list) if k == editing_item)
            items_list[old_idx] = (name, new_item)
            db[slot] = dict(items_list)
            slot_items = db[slot]
        else:
            slot_items[name] = new_item

        _save_db()
        st.session_state.pop("dev_edit_item", None)
        st.session_state.pop("dev_edit_slot", None)
        st.toast(f"{'Updated' if is_edit else 'Added'} '{name}' in {slot}", icon="✅")
        st.rerun()

# ---------------------------------------------------------------------------
# Danger zone
# ---------------------------------------------------------------------------
st.divider()
with st.expander("Danger Zone", expanded=False):
    st.warning("Reloading from disk will discard any unsaved in-memory changes.")
    if st.button("Reload DB from disk"):
        _load_db()
        st.toast("Reloaded gear_db.json from disk", icon="🔄")
        st.rerun()