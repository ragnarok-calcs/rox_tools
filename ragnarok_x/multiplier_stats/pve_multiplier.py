import dataclasses
from dataclasses import dataclass

# Multiplicative factors cannot drop below this floor.
_FLOOR = 0.2


# ---------------------------------------------------------------------------
# Stat dataclasses
# ---------------------------------------------------------------------------
@dataclass
class PlayerStats:
    patk: float                 # Physical Attack
    crit_dmg_bonus: float       # Crit DMG Bonus multiplier (e.g. 1.5 = +50% crit dmg)
    pdmg_bonus: float           # Flat P.DMG Bonus
    pdmg_bonus_pct: float       # % P.DMG Bonus (e.g. 0.20 = 20%)
    final_pdmg_bonus: float     # Final P.DMG Bonus
    elemental_counter: float    # Elemental Counter (e.g. 1.5 for counter element)
    element_enhance: float      # Element Enhance
    bonus_dmg_element: float    # Bonus DMG to Element
    bonus_dmg_race: float       # Bonus DMG to Race
    final_dmg_bonus: float      # Final DMG Bonus
    weapon_size_modifier: float # Weapon Size Modifier (e.g. 1.0 base)
    size_enhance: float         # Bonus DMG to Size
    total_final_pen: float = 0.0  # Total Final PEN (penetration mode only)


@dataclass
class TargetStats:
    crit_dmg_reduc: float       # Target's Crit DMG Reduction
    pdmg_reduc: float           # Target's flat P.DMG Reduction
    final_pdmg_reduc: float     # Target's Final P.DMG Reduction
    final_dmg_reduc: float      # Target's Final DMG Reduction
    total_final_def: float = 0.0  # Target's Total Final DEF (penetration mode only)


# ---------------------------------------------------------------------------
# Core functions
#
# Crit formula:
#   (P.ATK × (Crit DMG Bonus - Target Crit DMG Reduc)
#    + P.DMG Bonus × (1 + P.DMG Bonus%) - Target P.DMG Reduc)
#   × max(1 + Final P.DMG Bonus - Target Final P.DMG Reduc, 0.2)
#   × max(Elemental Counter + Element Enhance, 0.2)
#   × (1 + Bonus DMG to Element)
#   × (1 + Bonus DMG to Race)
#   × max(1 + Final DMG Bonus - Target Final DMG Reduc, 0.2)
#   × max(Weapon Size Modifier + Size Enhance, 0.2)
#
# Penetration formula replaces the ATK multiplier:
#   pen_diff = Total Final PEN - Target Total Final DEF
#   pen_mult = (1 + pen_diff)           if pen_diff <= 1.5
#            = (1 + pen_diff×2 - 1.5)   if pen_diff >  1.5
# ---------------------------------------------------------------------------
def _pen_multiplier(pen_diff: float) -> float:
    if pen_diff <= 1.5:
        return 1.0 + pen_diff
    return 1.0 + pen_diff * 2.0 - 1.5


def calculate_multiplier(
    player: PlayerStats, target: TargetStats, damage_type: str = "crit"
) -> float:
    """Return the overall PVE damage multiplier for the given player and target stats.

    damage_type: "crit" (default) or "pen" (penetration).
    """
    if damage_type == "pen":
        atk_mult = _pen_multiplier(player.total_final_pen - target.total_final_def)
    else:
        atk_mult = player.crit_dmg_bonus - target.crit_dmg_reduc

    base = (
        player.patk * atk_mult
        + player.pdmg_bonus * (1 + player.pdmg_bonus_pct)
        - target.pdmg_reduc
    )
    return (
        base
        * max(1 + player.final_pdmg_bonus - target.final_pdmg_reduc, _FLOOR)
        * max(player.elemental_counter + player.element_enhance, _FLOOR)
        * (1 + player.bonus_dmg_element)
        * (1 + player.bonus_dmg_race)
        * max(1 + player.final_dmg_bonus - target.final_dmg_reduc, _FLOOR)
        * max(player.weapon_size_modifier + player.size_enhance, _FLOOR)
    )


def modifier_weights(
    player: PlayerStats, target: TargetStats, damage_type: str = "crit"
) -> dict[str, float]:
    """
    Return the marginal value of each player stat via finite differences.

    Uses calculate_multiplier (with floored factors) so weights automatically
    drop to 0 for any stat whose factor is pinned at the 0.2 floor.
    """
    base = calculate_multiplier(player, target, damage_type)
    eps = 1e-4
    return {
        field: (
            calculate_multiplier(
                dataclasses.replace(player, **{field: getattr(player, field) + eps}),
                target,
                damage_type,
            ) - base
        ) / eps
        for field in player.__dataclass_fields__
    }
