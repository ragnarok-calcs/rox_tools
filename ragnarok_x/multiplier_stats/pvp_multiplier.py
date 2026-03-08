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
    weapon_size_modifier: float # Weapon Size Modifier (e.g. 1.0 base)
    size_enhance: float         # Bonus DMG to Size
    bonus_dmg_race: float       # Bonus DMG to Race
    elemental_counter: float    # Elemental Counter (e.g. 1.5 for counter element)
    element_enhance: float      # Element Enhance
    final_dmg_bonus: float      # Final DMG Bonus
    pvp_final_pdmg_bonus: float # PVP Final P.DMG Bonus
    pvp_pdmg_bonus: float       # PVP P.DMG Bonus (flat additive, outside all factors)


@dataclass
class TargetStats:
    crit_dmg_reduc: float       # Target's Crit DMG Reduction
    pdmg_reduc: float           # Target's flat P.DMG Reduction
    final_pdmg_reduc: float     # Target's Final P.DMG Reduction
    element_resist: float       # Target's Element Resist
    size_reduc: float           # Target's Size Reduction
    race_reduc: float           # Target's Race Reduction
    final_dmg_reduc: float      # Target's Final DMG Reduction
    pvp_pdmg_reduc: float       # Target's PVP P.DMG Reduction
    pvp_final_pdmg_reduc: float # Target's PVP Final P.DMG Reduction


# ---------------------------------------------------------------------------
# Core functions
#
# Full formula:
#   (8 × (
#       (P.ATK × (Crit DMG Bonus - Target Crit DMG Reduc)
#        + P.DMG Bonus × (1 + P.DMG Bonus%) - Target P.DMG Reduc)
#       × max(1 + Final P.DMG Bonus - Target Final P.DMG Reduc, 0.2)
#       × max(Weapon Size Modifier + Size Enhance - Size Reduction, 0.2)
#       × max(1 + Bonus DMG to Race - Race Reduction, 0.2)
#       × max(Elemental Counter + Element Enhance - Element Resist, 0.2)
#       × max(1 + Final DMG Bonus - Target Final DMG Reduc, 0.2)
#   ) ^ 0.6 - Target PVP P.DMG Reduc)
#   × max(1 + PVP Final P.DMG Bonus - Target PVP Final P.DMG Reduc, 0.2)
#   + PVP P.DMG Bonus
# ---------------------------------------------------------------------------
def calculate_multiplier(player: PlayerStats, target: TargetStats) -> float:
    """Return the overall PVP damage multiplier for the given player and target stats."""
    base = (
        player.patk * (player.crit_dmg_bonus - target.crit_dmg_reduc)
        + player.pdmg_bonus * (1 + player.pdmg_bonus_pct)
        - target.pdmg_reduc
    )
    inner = (
        base
        * max(1 + player.final_pdmg_bonus - target.final_pdmg_reduc, _FLOOR)
        * max(player.weapon_size_modifier + player.size_enhance - target.size_reduc, _FLOOR)
        * max(1 + player.bonus_dmg_race - target.race_reduc, _FLOOR)
        * max(player.elemental_counter + player.element_enhance - target.element_resist, _FLOOR)
        * max(1 + player.final_dmg_bonus - target.final_dmg_reduc, _FLOOR)
    )
    return (
        (8 * inner ** 0.6 - target.pvp_pdmg_reduc)
        * max(1 + player.pvp_final_pdmg_bonus - target.pvp_final_pdmg_reduc, _FLOOR)
        + player.pvp_pdmg_bonus
    )


def modifier_weights(player: PlayerStats, target: TargetStats) -> dict[str, float]:
    """
    Return the marginal value of each player stat via finite differences.

    Uses calculate_multiplier (with floored factors) so weights automatically
    drop to 0 for any stat whose factor is pinned at the 0.2 floor.
    Note: stats inside the ^0.6 term have diminishing returns.
    """
    base = calculate_multiplier(player, target)
    eps = 1e-4
    return {
        field: (
            calculate_multiplier(
                dataclasses.replace(player, **{field: getattr(player, field) + eps}),
                target,
            ) - base
        ) / eps
        for field in player.__dataclass_fields__
    }