"""
Card Optimizer — Ragnarok X: Next Generation
---------------------------------------------
Optimizes card slot assignments to maximize PVP damage output.
Users select available cards, configure equipment slot counts,
enter base/target stats, and the optimizer finds the best assignment.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from collections import Counter
import streamlit as st
from data.cards_db import CARDS_DB, CARD_SLOT_TYPES
from multiplier_stats import (
    PVPPlayerStats, PVPTargetStats,
    pvp_calculate_multiplier,
)

st.set_page_config(page_title="Card Optimizer", layout="wide")
st.title("Card Optimizer")
st.caption(
    "Optimize card slot assignments to maximize PVP damage. "
    "Add your available cards, configure equipment slots, enter stats, and hit Optimize."
)

# ---------------------------------------------------------------------------
# Stat definitions (PVP-relevant, matches DMG_Multiplier conventions)
# ---------------------------------------------------------------------------
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
    'pdmg_reduc':           ('P.DMG Reduction',             0),
    'final_pdmg_reduc':     ('Final P.DMG Reduction %',     0),
    'element_resist':       ('Element Resist %',             0),
    'size_reduc':           ('Size Reduction %',             0),
    'race_reduc':           ('Race Reduction %',             0),
    'final_dmg_reduc':      ('Final DMG Reduction %',        0),
    'pvp_pdmg_reduc':       ('PVP P.DMG Reduction',          0),
    'pvp_final_pdmg_reduc': ('PVP Final P.DMG Reduction %',  0),
    'total_final_def':      ('Total Final DEF %',            0),
}

_PCT_FIELDS = {
    'crit_dmg_bonus', 'final_pdmg_bonus', 'weapon_size_modifier', 'size_enhance',
    'bonus_dmg_race', 'elemental_counter', 'element_enhance', 'bonus_dmg_element',
    'final_dmg_bonus', 'pvp_final_pdmg_bonus',
    'total_final_pen',
    'crit_dmg_reduc', 'final_pdmg_reduc', 'element_resist', 'size_reduc',
    'race_reduc', 'final_dmg_reduc', 'pvp_final_pdmg_reduc',
    'total_final_def',
}

_INT_FIELDS = {'patk', 'pdmg_bonus', 'pdmg_bonus_pct', 'pdmg_reduc', 'pvp_pdmg_bonus', 'pvp_pdmg_reduc'}

_SELECT_FIELDS = {
    'weapon_size_modifier': [75, 100],
    'elemental_counter':    [0, 25, 50, 70, 75, 90, 100, 125, 150, 175],
}

# Equipment slots: {name: (card_type, min_slots, max_slots, default_slots)}
EQUIPMENT_SLOTS = {
    "Main Hand":       ("weapon",     2, 3, 2),
    "Off-Hand":        ("weapon",     1, 2, 1),
    "Clothes":         ("armor",      1, 2, 1),
    "Cloak":           ("armor",      1, 2, 1),
    "Shoes":           ("armor",      1, 2, 1),
    "Accessory Left":  ("decoration", 1, 2, 1),
    "Accessory Right": ("decoration", 1, 2, 1),
    "Talisman":        ("decoration", 1, 2, 1),
    "Head":            ("costume",    1, 2, 1),
    "Face":            ("costume",    1, 2, 1),
    "Mouth":           ("costume",    1, 2, 1),
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _stat_line(stats: dict) -> str:
    parts = [f"{STAT_LABELS.get(k, k)} {v:+g}" for k, v in stats.items() if v != 0]
    return ",  ".join(parts) if parts else "—"


def _pct_to_decimal(vals: dict) -> dict:
    return {k: v / 100.0 if k in _PCT_FIELDS else v for k, v in vals.items()}


def _field_key(prefix: str, field: str) -> str:
    return f"{prefix}_{field}"


def _render_input(field: str, label: str, default, key: str):
    if field in _SELECT_FIELDS:
        options = _SELECT_FIELDS[field]
        idx = options.index(int(default)) if int(default) in options else 0
        return st.selectbox(label, options=options, index=idx, format_func=lambda x: f"{x}%", key=key)
    elif field in _PCT_FIELDS or field in _INT_FIELDS:
        return st.number_input(label, value=int(default), min_value=0, step=1, key=key)
    else:
        return st.number_input(label, value=default, min_value=0.0, key=key)


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
if "co_card_collection" not in st.session_state:
    st.session_state["co_card_collection"] = []
if "player_builds" not in st.session_state:
    st.session_state["player_builds"] = {}
if "co_results" not in st.session_state:
    st.session_state["co_results"] = None

# ---------------------------------------------------------------------------
# Section 1: Card Collection
# ---------------------------------------------------------------------------
_real_cards = {n: c for n, c in CARDS_DB.items() if n != "None"}

with st.expander(f"**Card Collection** ({len(st.session_state['co_card_collection'])} cards)", expanded=True):
    col_add, col_btn = st.columns([4, 1])
    with col_add:
        card_to_add = st.selectbox(
            "Add card", list(_real_cards.keys()),
            key="co_card_select", label_visibility="collapsed",
        )
    with col_btn:
        if st.button("Add", use_container_width=True, key="co_add_btn"):
            st.session_state["co_card_collection"].append(card_to_add)
            st.rerun()

    collection = st.session_state["co_card_collection"]
    if collection:
        for slot_type in CARD_SLOT_TYPES:
            type_cards = [c for c in collection if CARDS_DB[c]["slot_type"] == slot_type]
            if not type_cards:
                continue
            st.markdown(f"**{slot_type.title()}** ({len(type_cards)})")
            counts = Counter(type_cards)
            for card_name, count in sorted(counts.items()):
                stats = CARDS_DB[card_name]["stats"]
                col_info, col_rm = st.columns([5, 1])
                with col_info:
                    qty = f"x{count}" if count > 1 else ""
                    st.caption(f"{card_name} {qty}  |  {_stat_line(stats)}")
                with col_rm:
                    if st.button("X", key=f"co_rm_{slot_type}_{card_name}", use_container_width=True):
                        st.session_state["co_card_collection"].remove(card_name)
                        st.rerun()
    else:
        st.info("Add cards from the dropdown above.")

# ---------------------------------------------------------------------------
# Section 2: Equipment Slot Configuration
# ---------------------------------------------------------------------------
with st.expander("**Equipment Slots**", expanded=False):
    slot_config = {}
    for card_type in CARD_SLOT_TYPES:
        type_equips = {name: cfg for name, cfg in EQUIPMENT_SLOTS.items() if cfg[0] == card_type}
        st.markdown(f"**{card_type.title()} Slots**")
        cols = st.columns(len(type_equips))
        for i, (equip_name, (_, mn, mx, default)) in enumerate(type_equips.items()):
            with cols[i]:
                val = st.number_input(
                    equip_name, min_value=mn, max_value=mx, value=default, step=1,
                    key=f"co_slot_{equip_name.replace(' ', '_')}",
                )
                slot_config[equip_name] = val

# ---------------------------------------------------------------------------
# Section 3: Base Player Stats (without cards)
# ---------------------------------------------------------------------------
with st.expander("**Player Stats (without cards)**", expanded=False):
    builds = st.session_state.get("player_builds", {})
    pvp_builds = {n: b for n, b in builds.items() if b.get("mode") == "PVP"}
    if pvp_builds:
        build_choice = st.selectbox(
            "Load saved PVP build", ["(manual entry)"] + list(pvp_builds.keys()),
            key="co_build_select",
        )
        if build_choice != "(manual entry)":
            build_stats = pvp_builds[build_choice]["stats"]
            for field, (_, default) in _PVP_PLAYER_FIELDS.items():
                val = build_stats.get(field, default)
                sk = _field_key("co_p", field)
                if field in _SELECT_FIELDS:
                    st.session_state[sk] = int(val)
                elif field in _PCT_FIELDS or field in _INT_FIELDS:
                    st.session_state[sk] = int(val)
                else:
                    st.session_state[sk] = float(val)

    cols = st.columns(2)
    p_idx = 0
    for field, (label, default) in _PVP_PLAYER_FIELDS.items():
        with cols[p_idx % 2]:
            _render_input(field, label, default, _field_key("co_p", field))
        p_idx += 1

# ---------------------------------------------------------------------------
# Section 4: Target Stats
# ---------------------------------------------------------------------------
with st.expander("**Target Stats**", expanded=False):
    cols = st.columns(2)
    t_idx = 0
    for field, (label, default) in _PVP_TARGET_FIELDS.items():
        with cols[t_idx % 2]:
            _render_input(field, label, default, _field_key("co_t", field))
        t_idx += 1

# ---------------------------------------------------------------------------
# Section 5: Damage Type
# ---------------------------------------------------------------------------
dmg_type = st.radio("Damage Type", ["crit", "pen"], horizontal=True, key="co_dmg_type",
                     format_func=lambda x: "Crit" if x == "crit" else "Penetration")

# ---------------------------------------------------------------------------
# Optimization engine
# ---------------------------------------------------------------------------
def _read_player_vals() -> dict:
    return {
        field: st.session_state.get(_field_key("co_p", field), default)
        for field, (_, default) in _PVP_PLAYER_FIELDS.items()
    }


def _read_target_vals() -> dict:
    return {
        field: st.session_state.get(_field_key("co_t", field), default)
        for field, (_, default) in _PVP_TARGET_FIELDS.items()
    }


def _add_stats(base: dict, card_stats: dict) -> dict:
    result = dict(base)
    for k, v in card_stats.items():
        if k in result:
            result[k] += v
    return result


def _eval_multiplier(player_vals: dict, target_vals: dict, damage_type: str) -> float:
    p_dec = _pct_to_decimal(player_vals)
    t_dec = _pct_to_decimal(target_vals)
    return pvp_calculate_multiplier(PVPPlayerStats(**p_dec), PVPTargetStats(**t_dec), damage_type)


def _sum_card_stats(card_names: tuple) -> dict:
    totals = {}
    for name in card_names:
        if name == "None":
            continue
        for k, v in CARDS_DB[name]["stats"].items():
            totals[k] = totals.get(k, 0) + v
    return totals


def _generate_assignments(card_counts: dict, n_slots: int):
    """Generate all ways to fill n_slots from available cards (respecting ownership counts)."""
    card_names = list(card_counts.keys())

    def _recurse(idx, remaining, current):
        if remaining == 0:
            yield tuple(current)
            return
        if idx >= len(card_names):
            yield tuple(current) + ("None",) * remaining
            return
        name = card_names[idx]
        for use in range(min(card_counts[name], remaining) + 1):
            yield from _recurse(idx + 1, remaining - use, current + [name] * use)

    yield from _recurse(0, n_slots, [])


def _is_dominated(vec_a: dict, vec_b: dict, relevant_stats: set) -> bool:
    """Return True if vec_a dominates vec_b (a >= b for all relevant stats)."""
    for s in relevant_stats:
        if vec_a.get(s, 0) < vec_b.get(s, 0):
            return False
    return True


def _prune_dominated(stat_combos: list, relevant_stats: set) -> list:
    """Remove dominated stat vectors. Each entry is (stat_dict, assignment_tuple)."""
    pruned = []
    for candidate in stat_combos:
        dominated = False
        new_pruned = []
        for existing in pruned:
            if _is_dominated(existing[0], candidate[0], relevant_stats):
                dominated = True
                new_pruned.append(existing)
            elif _is_dominated(candidate[0], existing[0], relevant_stats):
                continue  # candidate dominates existing, drop existing
            else:
                new_pruned.append(existing)
        if not dominated:
            new_pruned.append(candidate)
        pruned = new_pruned
    return pruned


def _optimize(base_player: dict, target_vals: dict, collection: list, slot_config: dict, damage_type: str):
    """Find the optimal card assignment to maximize PVP damage."""
    # Relevant PVP player stats (from the dataclass)
    pvp_stats = set(PVPPlayerStats.__dataclass_fields__.keys())

    # Group cards by slot_type
    cards_by_type = {}
    for card_name in collection:
        ctype = CARDS_DB[card_name]["slot_type"]
        if ctype not in cards_by_type:
            cards_by_type[ctype] = []
        cards_by_type[ctype].append(card_name)

    # Total slots per card type
    slots_by_type = {}
    equip_by_type = {}
    for equip_name, n_slots in slot_config.items():
        ctype = EQUIPMENT_SLOTS[equip_name][0]
        slots_by_type[ctype] = slots_by_type.get(ctype, 0) + n_slots
        if ctype not in equip_by_type:
            equip_by_type[ctype] = []
        equip_by_type[ctype].append((equip_name, n_slots))

    # Generate per-group options
    group_options = {}
    for card_type in CARD_SLOT_TYPES:
        n_slots = slots_by_type.get(card_type, 0)
        if n_slots == 0:
            group_options[card_type] = [({}, ())]
            continue

        owned = Counter(cards_by_type.get(card_type, []))
        combos = list(_generate_assignments(dict(owned), n_slots))
        stat_combos = [(_sum_card_stats(combo), combo) for combo in combos]

        # Prune dominated
        stat_combos = _prune_dominated(stat_combos, pvp_stats)
        group_options[card_type] = stat_combos

    # Cross-group search
    total_combos = 1
    for opts in group_options.values():
        total_combos *= len(opts)

    types = CARD_SLOT_TYPES
    best_mult = -1
    best_assignment = None
    best_card_stats = None

    if total_combos <= 500_000:
        # Exhaustive search
        for w_stats, w_combo in group_options[types[0]]:
            for a_stats, a_combo in group_options[types[1]]:
                for d_stats, d_combo in group_options[types[2]]:
                    for c_stats, c_combo in group_options[types[3]]:
                        combined = dict(base_player)
                        for s in (w_stats, a_stats, d_stats, c_stats):
                            for k, v in s.items():
                                if k in combined:
                                    combined[k] += v
                        mult = _eval_multiplier(combined, target_vals, damage_type)
                        if mult > best_mult:
                            best_mult = mult
                            best_assignment = {
                                types[0]: w_combo,
                                types[1]: a_combo,
                                types[2]: d_combo,
                                types[3]: c_combo,
                            }
                            total_card = {}
                            for s in (w_stats, a_stats, d_stats, c_stats):
                                for k, v in s.items():
                                    total_card[k] = total_card.get(k, 0) + v
                            best_card_stats = total_card
    else:
        # Iterative greedy: fix 3 groups, optimize 1 at a time
        current = {t: group_options[t][0] for t in types}
        improved = True
        while improved:
            improved = False
            for opt_type in types:
                best_local = -1
                best_choice = current[opt_type]
                for candidate in group_options[opt_type]:
                    combined = dict(base_player)
                    for t in types:
                        chosen = candidate if t == opt_type else current[t]
                        for k, v in chosen[0].items():
                            if k in combined:
                                combined[k] += v
                    mult = _eval_multiplier(combined, target_vals, damage_type)
                    if mult > best_local:
                        best_local = mult
                        best_choice = candidate
                if best_choice != current[opt_type]:
                    current[opt_type] = best_choice
                    improved = True

        best_mult = -1
        combined = dict(base_player)
        total_card = {}
        for t in types:
            for k, v in current[t][0].items():
                if k in combined:
                    combined[k] += v
                total_card[k] = total_card.get(k, 0) + v
        best_mult = _eval_multiplier(combined, target_vals, damage_type)
        best_assignment = {t: current[t][1] for t in types}
        best_card_stats = total_card

    # Map card assignments back to equipment pieces
    equip_assignments = {}
    for card_type in types:
        cards_flat = list(best_assignment.get(card_type, ()))
        for equip_name, n_slots in equip_by_type.get(card_type, []):
            equip_assignments[equip_name] = cards_flat[:n_slots]
            cards_flat = cards_flat[n_slots:]

    return best_mult, equip_assignments, best_card_stats


# ---------------------------------------------------------------------------
# Section 6: Optimize button & results
# ---------------------------------------------------------------------------
st.divider()
col_opt, col_reset = st.columns([1, 1])
with col_opt:
    run_optimize = st.button("Optimize", use_container_width=True, type="primary")
with col_reset:
    if st.button("Reset Results", use_container_width=True):
        st.session_state["co_results"] = None
        st.rerun()

if run_optimize:
    collection = st.session_state["co_card_collection"]
    if not collection:
        st.warning("Add cards to your collection first.")
    else:
        player_vals = _read_player_vals()
        target_vals = _read_target_vals()

        # Read slot config from session
        sc = {}
        for equip_name, (_, mn, mx, default) in EQUIPMENT_SLOTS.items():
            sc[equip_name] = st.session_state.get(
                f"co_slot_{equip_name.replace(' ', '_')}", default
            )

        base_mult = _eval_multiplier(player_vals, target_vals, dmg_type)

        with st.spinner("Optimizing..."):
            best_mult, equip_assignments, card_stats = _optimize(
                player_vals, target_vals, collection, sc, dmg_type
            )

        st.session_state["co_results"] = {
            "best_mult": best_mult,
            "base_mult": base_mult,
            "assignments": equip_assignments,
            "card_stats": card_stats,
        }
        st.rerun()

# ---------------------------------------------------------------------------
# Display results
# ---------------------------------------------------------------------------
results = st.session_state.get("co_results")
if results:
    st.divider()
    st.markdown("### Results")

    base_mult = results["base_mult"]
    best_mult = results["best_mult"]
    improvement = ((best_mult - base_mult) / base_mult * 100) if base_mult != 0 else 0

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric("Optimal Multiplier", f"{best_mult:,.2f}")
    with col_m2:
        st.metric("Base (no cards)", f"{base_mult:,.2f}")
    with col_m3:
        st.metric("Improvement", f"+{improvement:.1f}%")

    st.markdown("#### Card Assignments")
    for equip_name in EQUIPMENT_SLOTS:
        cards = results["assignments"].get(equip_name, [])
        card_type = EQUIPMENT_SLOTS[equip_name][0]
        display_cards = [c for c in cards if c != "None"]
        if display_cards:
            st.caption(f"**{equip_name}** ({card_type}): {', '.join(display_cards)}")
        else:
            st.caption(f"**{equip_name}** ({card_type}): —")

    card_stats = results.get("card_stats", {})
    if card_stats:
        st.markdown("#### Total Card Stats")
        stat_items = [(k, v) for k, v in card_stats.items() if v != 0]
        if stat_items:
            cols = st.columns(2)
            mid = (len(stat_items) + 1) // 2
            for col, chunk in [(cols[0], stat_items[:mid]), (cols[1], stat_items[mid:])]:
                with col:
                    for field, val in chunk:
                        st.metric(STAT_LABELS.get(field, field), f"+{val:g}")
