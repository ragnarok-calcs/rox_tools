"""
Card database — shared between Equipment Builder and Card Optimizer.

Each card has:
  - stats: dict[str, float]  (stat_field -> value in UI units)
  - slot_type: str  ("weapon", "armor", "decoration", "costume") or None for the "None" entry
"""

CARD_SLOT_TYPES = ["weapon", "armor", "decoration", "costume"]

CARDS_DB: dict[str, dict] = {
    "None":                   {"stats": {},                                              "slot_type": None},
    # ── Weapon ────────────────────────────────────────────────────────────────
    "Metaller Card":          {"stats": {"patk": 120},                                   "slot_type": "weapon"},
    "Orc Warrior Card":       {"stats": {"patk": 80,  "pdmg_bonus": 50},                 "slot_type": "weapon"},
    "Drake Card":             {"stats": {"patk": 60,  "size_enhance": 15},               "slot_type": "weapon"},
    "Phreeoni Card":          {"stats": {"crit_dmg_bonus": 15, "patk": 40},              "slot_type": "weapon"},
    "Minorous Card":          {"stats": {"bonus_dmg_race": 20},                          "slot_type": "weapon"},
    "Racial Boss Card":       {"stats": {"bonus_dmg_race": 25, "patk": 30},              "slot_type": "weapon"},
    "Hydra Card":             {"stats": {"bonus_dmg_race": 15, "final_pdmg_bonus": 3},   "slot_type": "weapon"},
    "Baphomet Jr Card":       {"stats": {"size_enhance": 20},                            "slot_type": "weapon"},
    "Vadon Card":             {"stats": {"bonus_dmg_element": 8},                        "slot_type": "weapon"},
    # ── Armor ─────────────────────────────────────────────────────────────────
    "Mummy Card":             {"stats": {"crit_dmg_bonus": 20},                          "slot_type": "armor"},
    "Willow Card":            {"stats": {"size_enhance": 10},                            "slot_type": "armor"},
    "Verit Card":             {"stats": {"element_enhance": 10},                         "slot_type": "armor"},
    "Gloom Under Night Card": {"stats": {"final_pdmg_bonus": 8},                         "slot_type": "armor"},
    # ── Decoration ────────────────────────────────────────────────────────────
    "Evil Snake Lord Card":   {"stats": {"final_dmg_bonus": 8},                          "slot_type": "decoration"},
    "Maya Purple Card":       {"stats": {"pvp_pdmg_bonus": 200},                         "slot_type": "decoration"},
    # ── Costume ───────────────────────────────────────────────────────────────
    "Stormy Knight Card":     {"stats": {"pvp_final_pdmg_bonus": 10},                    "slot_type": "costume"},
}


def get_flat_cards_db() -> dict[str, dict]:
    """Return {name: {stat: value}} format for backward compatibility with Equipment Builder."""
    return {name: card["stats"] for name, card in CARDS_DB.items()}
