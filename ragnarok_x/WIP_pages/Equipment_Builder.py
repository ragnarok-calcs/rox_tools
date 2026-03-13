"""
Equipment Builder — Ragnarok X: Next Generation
------------------------------------------------
Lets a player assemble a build slot-by-slot (gear base stats, refine bonuses,
card stats, and enchants), then totals everything into the player-stat fields
used by the DMG Multiplier.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
from data.gear_db import GEAR_DB
from data.cards_db import get_flat_cards_db

st.set_page_config(page_title="Equipment Builder", layout="wide")
st.title("Equipment Builder")
st.caption(
    "Build your stat profile from gear, refines, cards, and enchants. "
    "The totals are saved as a player build you can load in the DMG Multiplier."
)

# ---------------------------------------------------------------------------
# Stat field definitions (mirrors DMG_Multiplier player stat fields)
# ---------------------------------------------------------------------------
STAT_FIELDS = [
    "patk",
    "crit_dmg_bonus",
    "pdmg_bonus",
    "pdmg_bonus_pct",
    "final_pdmg_bonus",
    "elemental_counter",
    "element_enhance",
    "bonus_dmg_element",
    "bonus_dmg_race",
    "final_dmg_bonus",
    "weapon_size_modifier",
    "size_enhance",
    "pvp_final_pdmg_bonus",
    "pvp_pdmg_bonus",
]

STAT_LABELS = {
    "patk":               "P.ATK",
    "crit_dmg_bonus":     "Crit DMG Bonus %",
    "pdmg_bonus":         "P.DMG Bonus",
    "pdmg_bonus_pct":     "P.DMG Bonus %",
    "final_pdmg_bonus":   "Final P.DMG Bonus %",
    "elemental_counter":  "Elemental Counter %",
    "element_enhance":    "Element Enhance %",
    "bonus_dmg_element":  "Bonus DMG to Element %",
    "bonus_dmg_race":     "Bonus DMG to Race %",
    "final_dmg_bonus":    "Final DMG Bonus %",
    "weapon_size_modifier": "Weapon Size Modifier %",
    "size_enhance":       "Bonus DMG to Size %",
    "pvp_final_pdmg_bonus": "PVP Final P.DMG Bonus %",
    "pvp_pdmg_bonus":     "PVP P.DMG Bonus",
}

def _blank() -> dict:
    return {f: 0.0 for f in STAT_FIELDS}

# ---------------------------------------------------------------------------
# Gear slot definitions
# ---------------------------------------------------------------------------
SLOTS = ["Weapon", "Off-Hand", "Armor", "Cloak", "Shoes",
         "Accessory 1", "Accessory 2", "Talisman 1", "Talisman 2"]

# Card database: {card_name: {stat_field: value}}  (from shared module)
CARDS_DB = get_flat_cards_db()

ENCHANT_POOLS: dict[str, list[str]] = {
    "Weapon / Off-Hand": [
        "patk", "pdmg_bonus", "pdmg_bonus_pct", "final_pdmg_bonus",
        "crit_dmg_bonus", "element_enhance", "bonus_dmg_element",
        "bonus_dmg_race", "size_enhance", "final_dmg_bonus",
        "pvp_final_pdmg_bonus", "pvp_pdmg_bonus",
    ],
    "Armor / Cloak / Shoes": [
        "patk", "pdmg_bonus", "pdmg_bonus_pct", "final_pdmg_bonus",
        "crit_dmg_bonus", "final_dmg_bonus", "bonus_dmg_race",
        "pvp_final_pdmg_bonus",
    ],
    "Accessory / Talisman": [
        "patk", "pdmg_bonus", "final_pdmg_bonus", "crit_dmg_bonus",
        "element_enhance", "bonus_dmg_element", "bonus_dmg_race",
        "size_enhance", "final_dmg_bonus", "pvp_final_pdmg_bonus", "pvp_pdmg_bonus",
    ],
}

SLOT_ENCHANT_POOL = {
    "Weapon":      "Weapon / Off-Hand",
    "Off-Hand":    "Weapon / Off-Hand",
    "Armor":       "Armor / Cloak / Shoes",
    "Cloak":       "Armor / Cloak / Shoes",
    "Shoes":       "Armor / Cloak / Shoes",
    "Accessory 1": "Accessory / Talisman",
    "Accessory 2": "Accessory / Talisman",
    "Talisman 1":  "Accessory / Talisman",
    "Talisman 2":  "Accessory / Talisman",
}

ENCHANT_RANGES: dict[str, list[int]] = {
    "patk":               [20,  40,  70, 100, 140],
    "pdmg_bonus":         [30,  60, 100, 150, 200],
    "pdmg_bonus_pct":     [ 1,   2,   3,   5,   7],
    "final_pdmg_bonus":   [ 1,   2,   3,   4,   5],
    "crit_dmg_bonus":     [ 3,   5,   8,  12,  15],
    "element_enhance":    [ 2,   3,   5,   7,  10],
    "bonus_dmg_element":  [ 2,   3,   5,   7,  10],
    "bonus_dmg_race":     [ 2,   3,   5,   8,  12],
    "size_enhance":       [ 2,   3,   5,   8,  12],
    "final_dmg_bonus":    [ 1,   2,   3,   5,   8],
    "pvp_final_pdmg_bonus": [2,  3,   5,   8,  12],
    "pvp_pdmg_bonus":     [30,  60, 100, 150, 200],
}

ENCHANT_TIERS = ["None", "Common", "Uncommon", "Rare", "Epic", "Excellent"]

SLOT_CARD_SLOTS = {
    "Weapon": 2, "Off-Hand": 1, "Armor": 1, "Cloak": 1, "Shoes": 1,
    "Accessory 1": 1, "Accessory 2": 1, "Talisman 1": 1, "Talisman 2": 1,
}

SLOT_ENCHANT_SLOTS = {
    "Weapon": 3, "Off-Hand": 3, "Armor": 3, "Cloak": 3, "Shoes": 3,
    "Accessory 1": 2, "Accessory 2": 2, "Talisman 1": 2, "Talisman 2": 2,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _add(totals: dict, stats: dict):
    """Accumulate stat fields into totals; non-stat keys are silently ignored."""
    for k, v in stats.items():
        if k in totals:
            totals[k] += v

def _stat_line(stats: dict) -> str:
    parts = [f"{STAT_LABELS.get(k, k)} {v:+g}" for k, v in stats.items()
             if k in STAT_FIELDS and v != 0]
    return ",  ".join(parts) if parts else "—"

def _slot_key(slot: str, suffix: str) -> str:
    return f"eb_{slot.replace(' ', '_')}_{suffix}"

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
if "player_builds" not in st.session_state:
    st.session_state["player_builds"] = {}

# ---------------------------------------------------------------------------
# Build each slot
# ---------------------------------------------------------------------------
totals = _blank()
_two_handed_equipped = False

for slot in SLOTS:
    # Off-Hand locked when two-handed weapon is equipped
    if slot == "Off-Hand" and _two_handed_equipped:
        with st.expander(f"**{slot}** — locked (two-handed weapon)", expanded=False):
            st.info("Off-hand slot is occupied by the two-handed weapon.")
        continue

    slot_db   = GEAR_DB.get(slot, {"None": {"exclusive": {}, "base": {}, "upgrade": [{}], "refine": [{}]}})
    gear_opts = list(slot_db.keys())
    n_cards    = SLOT_CARD_SLOTS[slot]
    n_enchants = SLOT_ENCHANT_SLOTS[slot]
    pool_stats = ENCHANT_POOLS[SLOT_ENCHANT_POOL[slot]]

    with st.expander(f"**{slot}**", expanded=False):

        # ── Item & level selectors ──────────────────────────────────────────
        col_gear, col_upg, col_ref = st.columns([4, 1, 1])
        with col_gear:
            gear_choice = st.selectbox(
                "Item", gear_opts,
                key=_slot_key(slot, "gear"),
                label_visibility="collapsed",
            )

        item_data    = slot_db.get(gear_choice, slot_db["None"])
        exclusive    = item_data.get("exclusive", {})
        base         = item_data.get("base", {})
        upgrade_lvls = item_data.get("upgrade", [{}])
        refine_lvls  = item_data.get("refine", [{}])
        two_handed   = bool(item_data.get("two_handed", False))

        if slot == "Weapon":
            _two_handed_equipped = two_handed

        max_upg = len(upgrade_lvls) - 1
        max_ref = len(refine_lvls)  - 1   # 0..15 capped by table length

        with col_upg:
            upg_lvl = st.number_input(
                "Upg", min_value=0, max_value=max_upg, step=1,
                key=_slot_key(slot, "upgrade"),
                label_visibility="collapsed",
                help=f"Upgrade level (0–{max_upg})",
                disabled=(gear_choice == "None"),
            )
        with col_ref:
            ref_lvl = st.number_input(
                "Ref", min_value=0, max_value=max_ref, step=1,
                key=_slot_key(slot, "refine"),
                label_visibility="collapsed",
                help=f"Refine level (0–{max_ref})",
                disabled=(gear_choice == "None"),
            )

        upg_stats = upgrade_lvls[int(upg_lvl)] if upg_lvl <= max_upg else {}
        ref_stats = refine_lvls[int(ref_lvl)]  if ref_lvl  <= max_ref else {}

        # Accumulate into build totals
        _add(totals, exclusive)
        _add(totals, base)
        _add(totals, upg_stats)
        _add(totals, ref_stats)

        # ── Stat breakdown by section ───────────────────────────────────────
        if gear_choice != "None":
            c1, c2 = st.columns(2)
            with c1:
                st.caption(f"**Exclusive:** {_stat_line(exclusive)}")
                st.caption(f"**Base:** {_stat_line(base)}")
            with c2:
                st.caption(f"**Upgrade Lv.{int(upg_lvl)}:** {_stat_line(upg_stats)}")
                st.caption(f"**Refine +{int(ref_lvl)}:** {_stat_line(ref_stats)}")
            if two_handed:
                st.caption("Two-handed — Off-Hand slot locked")

        st.divider()

        # ── Cards ───────────────────────────────────────────────────────────
        st.markdown("**Cards**")
        card_options = list(CARDS_DB.keys())
        card_cols = st.columns(n_cards)
        for ci in range(n_cards):
            with card_cols[ci]:
                card = st.selectbox(
                    f"Card {ci + 1}", card_options,
                    key=_slot_key(slot, f"card{ci}"),
                    label_visibility="collapsed",
                )
                card_stats = CARDS_DB.get(card, {})
                _add(totals, card_stats)
                if card_stats:
                    st.caption(_stat_line(card_stats))

        st.divider()

        # ── Enchants ────────────────────────────────────────────────────────
        st.markdown("**Enchants**")
        for ei in range(n_enchants):
            enc_col_stat, enc_col_tier = st.columns([3, 2])
            with enc_col_stat:
                enc_stat = st.selectbox(
                    f"Enchant {ei + 1} stat",
                    ["None"] + pool_stats,
                    format_func=lambda s: "None" if s == "None" else STAT_LABELS.get(s, s),
                    key=_slot_key(slot, f"enc{ei}_stat"),
                    label_visibility="collapsed",
                )
            with enc_col_tier:
                enc_tier = st.selectbox(
                    f"Enchant {ei + 1} tier",
                    ENCHANT_TIERS,
                    key=_slot_key(slot, f"enc{ei}_tier"),
                    label_visibility="collapsed",
                    disabled=(enc_stat == "None"),
                )
            if enc_stat != "None" and enc_tier != "None":
                tier_idx = ENCHANT_TIERS.index(enc_tier) - 1
                enc_val  = ENCHANT_RANGES.get(enc_stat, [0] * 5)[tier_idx]
                _add(totals, {enc_stat: enc_val})
                st.caption(f"{STAT_LABELS.get(enc_stat, enc_stat)} +{enc_val:g}")

# ---------------------------------------------------------------------------
# Totals summary
# ---------------------------------------------------------------------------
st.divider()
st.markdown("### Build Totals")

active_stats = {k: v for k, v in totals.items() if v != 0}
if active_stats:
    col_a, col_b = st.columns(2)
    items = list(active_stats.items())
    mid = (len(items) + 1) // 2
    for col, chunk in [(col_a, items[:mid]), (col_b, items[mid:])]:
        with col:
            for field, val in chunk:
                st.metric(STAT_LABELS.get(field, field), f"{val:g}")
else:
    st.info("Select gear, cards, and enchants above to see totals.")

# ---------------------------------------------------------------------------
# Save as player build
# ---------------------------------------------------------------------------
st.divider()
st.markdown("### Save Build")
col_name, col_mode, col_save = st.columns([3, 1, 1])
with col_name:
    build_name = st.text_input(
        "Build name", placeholder="e.g. Swordsman BiS",
        label_visibility="collapsed", key="eb_build_name",
    )
with col_mode:
    build_mode = st.radio("Mode", ["PVE", "PVP"], horizontal=True, key="eb_mode")
with col_save:
    if st.button("💾 Save Build", use_container_width=True, type="primary"):
        name = build_name.strip()
        if not name:
            st.toast("Enter a build name.", icon="❌")
        elif not active_stats:
            st.toast("Build has no stats to save.", icon="❌")
        else:
            overwrite = name in st.session_state["player_builds"]
            st.session_state["player_builds"][name] = {
                "mode":  build_mode,
                "stats": {k: float(v) for k, v in active_stats.items()},
            }
            st.toast(f"{'Updated' if overwrite else 'Saved'} '{name}'", icon="✅")
