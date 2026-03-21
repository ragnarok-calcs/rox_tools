"""
enchants_data.py
----------------
Helpers for enchants_db.json and awakenings_db.json.
Used by the Enchant Optimizer and Build Editor.
"""

import json
from pathlib import Path
import pandas as pd

_ENCHANTS_PATH   = Path(__file__).parent / "enchants_db.json"
_AWAKENINGS_PATH = Path(__file__).parent / "awakenings_db.json"

# enchants_db stat_en → OFFENSIVE_FIELDS key (damage-relevant stats only)
ENCHANT_STAT_FIELD_MAP: dict[str, str] = {
    "DMG Bonus":                    "pdmg_bonus",
    "DMG Bonus %":                  "pdmg_bonus_pct",
    "Final P.DMG/M.DMG Bonus %":    "final_pdmg_bonus",
    "Final Pen %":                  "total_final_pen",
    "[Element] Enhancement":        "element_enhance",
    "[Race] Monster DMG Inc":       "bonus_dmg_race",
    "PvP Final P.DMG/M.DMG Bonus":  "pvp_final_pdmg_bonus",
    "PvP P.DMG/M.DMG Bonus":        "pvp_pdmg_bonus",
}

# Human-readable stat labels (for UI display)
ENCHANT_STAT_LABELS: dict[str, str] = {
    "DMG Bonus":                    "P.DMG/M.DMG Bonus",
    "DMG Bonus %":                  "P.DMG/M.DMG Bonus %",
    "Final P.DMG/M.DMG Bonus %":    "Final P.DMG/M.DMG Bonus %",
    "Final Pen %":                  "Final PEN %",
    "[Element] Enhancement":        "Element Enhance %",
    "[Race] Monster DMG Inc":       "Bonus DMG to Race %",
    "PvP Final P.DMG/M.DMG Bonus":  "PVP Final P.DMG/M.DMG Bonus %",
    "PvP P.DMG/M.DMG Bonus":        "PVP P.DMG/M.DMG Bonus",
}

# enchants_db equipment_en values per logical weapon type
WEAPON_EQUIP_LABEL: dict[str, str] = {
    "one-handed": "One-handed Weapon",
    "two-handed":  "Two-handed Weapon",
    "sub":         "Sub-weapon",
}

QUALITY_OPTIONS = ["White", "Blue", "Purple", "Orange"]
_QUALITY_COL    = {"White": "white", "Blue": "blue", "Purple": "purple", "Orange": "orange"}


def _load_awakenings() -> list[dict]:
    with open(_AWAKENINGS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_enchants() -> pd.DataFrame:
    with open(_ENCHANTS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    for col in ("level", "white", "blue", "purple", "orange"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


_AWAKENINGS_DATA = _load_awakenings()
_ENCHANTS_DF     = _load_enchants()

_ENCHANT_AWAKENING_TABLE: dict[int, dict] = {
    row["Awakening Level"]: {
        "enchant_lvl": row["Enchant Lvl"],
        "modifier":    row["Modifier"],
    }
    for row in _AWAKENINGS_DATA
    if row.get("Awakening") == "Enchant"
}
MAX_ENCHANT_AWAKENING = max(_ENCHANT_AWAKENING_TABLE.keys(), default=0)


def get_max_awakening_for_enchant_levels(weapon_lvl: int, armor_lvl: int, accessory_lvl: int) -> int:
    """
    Return the highest enchant awakening level achievable given the three enchant levels.
    All three must meet the required 'Enchant Lvl' for a given awakening tier.
    """
    min_lvl = min(weapon_lvl, armor_lvl, accessory_lvl)
    max_awk = 0
    for awk_lvl, info in _ENCHANT_AWAKENING_TABLE.items():
        if info["enchant_lvl"] <= min_lvl:
            max_awk = max(max_awk, awk_lvl)
    return max_awk


def get_enchant_awakening_info(awakening_level: int) -> dict:
    """Return {enchant_lvl, modifier} for the given enchant awakening level (0 = none)."""
    if awakening_level <= 0:
        return {"enchant_lvl": 1, "modifier": 1.0}
    return _ENCHANT_AWAKENING_TABLE.get(
        awakening_level,
        {"enchant_lvl": 1, "modifier": 1.0},
    )


def get_enchant_cities_for_stat(weapon_type: str, stat_en: str) -> list[str]:
    """
    Return a sorted list of cities that offer stat_en for the given weapon type.
    Returns a single-element list when only one city carries that enchant.
    """
    equip_label = WEAPON_EQUIP_LABEL.get(weapon_type)
    if equip_label is None:
        return []
    mask = (
        (_ENCHANTS_DF["equipment_en"] == equip_label) &
        (_ENCHANTS_DF["stat_en"] == stat_en)
    )
    return sorted(_ENCHANTS_DF[mask]["location"].dropna().unique().tolist())


def get_weapon_enchant_options(
    weapon_type: str,
    enchant_level: int,
    quality: str,
    modifier: float = 1.0,
    city: str | None = None,
) -> list[dict]:
    """
    Return deduplicated list of {stat_en, field, effective_value} for
    damage-relevant weapon enchants at the given level and quality.

    When city is None the highest base value across all cities is used.
    When city is provided only rows from that city are considered.

    weapon_type: "one-handed", "two-handed", or "sub"
    """
    equip_label = WEAPON_EQUIP_LABEL.get(weapon_type)
    if equip_label is None:
        return []
    quality_col = _QUALITY_COL.get(quality, "orange")

    mask = (
        (_ENCHANTS_DF["equipment_en"] == equip_label) &
        (_ENCHANTS_DF["level"] == enchant_level) &
        (_ENCHANTS_DF[quality_col].notna()) &
        (_ENCHANTS_DF["stat_en"].isin(ENCHANT_STAT_FIELD_MAP))
    )
    if city is not None:
        mask = mask & (_ENCHANTS_DF["location"] == city)

    rows = _ENCHANTS_DF[mask]
    if rows.empty:
        return []

    best = rows.groupby("stat_en")[quality_col].max().reset_index()
    options = []
    for _, row in best.iterrows():
        stat_en = row["stat_en"]
        raw_val = float(row[quality_col])
        eff_val = round(raw_val * modifier, 4)
        options.append({
            "stat_en":         stat_en,
            "field":           ENCHANT_STAT_FIELD_MAP[stat_en],
            "raw_value":       raw_val,
            "effective_value": eff_val,
        })
    return options
