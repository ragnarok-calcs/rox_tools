from dataclasses import dataclass
from sympy import symbols, diff

# ---------------------------------------------------------------------------
# Symbolic setup (module-level — derivatives computed once at import)
#
# Full formula:
#   (P.ATK × (Crit DMG Bonus - Target Crit DMG Reduc)
#    + P.DMG Bonus × (1 + P.DMG Bonus%) - Target P.DMG Reduc)
#   × (1 + Final P.DMG Bonus - Target Final P.DMG Reduc)
#   × (Elemental Counter + Element Enhance)
#   × (1 + Bonus DMG to Element)
#   × (1 + Bonus DMG to Race)
#   × (1 + Final DMG Bonus - Target Final DMG Reduc)
#   × (Weapon Size Modifier + Size Enhance)
# ---------------------------------------------------------------------------

# Player symbols
_PATK, _CRIT_BONUS, _PDMG_BONUS, _PDMG_BONUS_PCT = symbols(
    'patk crit_dmg_bonus pdmg_bonus pdmg_bonus_pct', positive=True
)
_FINAL_PDMG_BONUS, _ELEM_COUNTER, _ELEM_ENHANCE = symbols(
    'final_pdmg_bonus elemental_counter element_enhance', nonnegative=True
)
_BONUS_ELEM, _BONUS_RACE, _FINAL_DMG_BONUS = symbols(
    'bonus_dmg_element bonus_dmg_race final_dmg_bonus', nonnegative=True
)
_WEAPON_SIZE_MOD, _SIZE_ENHANCE = symbols(
    'weapon_size_modifier size_enhance', nonnegative=True
)

# Target symbols
_CRIT_REDUC, _PDMG_REDUC, _FINAL_PDMG_REDUC, _FINAL_DMG_REDUC = symbols(
    'crit_dmg_reduc pdmg_reduc final_pdmg_reduc final_dmg_reduc', nonnegative=True
)

_BASE = (
    _PATK * (_CRIT_BONUS - _CRIT_REDUC)
    + _PDMG_BONUS * (1 + _PDMG_BONUS_PCT)
    - _PDMG_REDUC
)

_EXPR = (
    _BASE
    * (1 + _FINAL_PDMG_BONUS - _FINAL_PDMG_REDUC)
    * (_ELEM_COUNTER + _ELEM_ENHANCE)
    * (1 + _BONUS_ELEM)
    * (1 + _BONUS_RACE)
    * (1 + _FINAL_DMG_BONUS - _FINAL_DMG_REDUC)
    * (_WEAPON_SIZE_MOD + _SIZE_ENHANCE)
)

_PLAYER_SYMS = {
    'patk':                 _PATK,
    'crit_dmg_bonus':       _CRIT_BONUS,
    'pdmg_bonus':           _PDMG_BONUS,
    'pdmg_bonus_pct':       _PDMG_BONUS_PCT,
    'final_pdmg_bonus':     _FINAL_PDMG_BONUS,
    'elemental_counter':    _ELEM_COUNTER,
    'element_enhance':      _ELEM_ENHANCE,
    'bonus_dmg_element':    _BONUS_ELEM,
    'bonus_dmg_race':       _BONUS_RACE,
    'final_dmg_bonus':      _FINAL_DMG_BONUS,
    'weapon_size_modifier': _WEAPON_SIZE_MOD,
    'size_enhance':         _SIZE_ENHANCE,
}

_WEIGHT_EXPRS = {name: diff(_EXPR, sym) for name, sym in _PLAYER_SYMS.items()}


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
    size_enhance: float         # Size Enhance


@dataclass
class TargetStats:
    crit_dmg_reduc: float       # Target's Crit DMG Reduction
    pdmg_reduc: float           # Target's flat P.DMG Reduction
    final_pdmg_reduc: float     # Target's Final P.DMG Reduction
    final_dmg_reduc: float      # Target's Final DMG Reduction


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------
def _subs_map(player: PlayerStats, target: TargetStats) -> dict:
    return {
        _PATK:             player.patk,
        _CRIT_BONUS:       player.crit_dmg_bonus,
        _PDMG_BONUS:       player.pdmg_bonus,
        _PDMG_BONUS_PCT:   player.pdmg_bonus_pct,
        _FINAL_PDMG_BONUS: player.final_pdmg_bonus,
        _ELEM_COUNTER:     player.elemental_counter,
        _ELEM_ENHANCE:     player.element_enhance,
        _BONUS_ELEM:       player.bonus_dmg_element,
        _BONUS_RACE:       player.bonus_dmg_race,
        _FINAL_DMG_BONUS:  player.final_dmg_bonus,
        _WEAPON_SIZE_MOD:  player.weapon_size_modifier,
        _SIZE_ENHANCE:     player.size_enhance,
        _CRIT_REDUC:       target.crit_dmg_reduc,
        _PDMG_REDUC:       target.pdmg_reduc,
        _FINAL_PDMG_REDUC: target.final_pdmg_reduc,
        _FINAL_DMG_REDUC:  target.final_dmg_reduc,
    }


def calculate_multiplier(player: PlayerStats, target: TargetStats) -> float:
    """Return the overall damage multiplier for the given player and target stats."""
    return float(_EXPR.subs(_subs_map(player, target)))


def modifier_weights(player: PlayerStats, target: TargetStats) -> dict[str, float]:
    """
    Return the marginal value of each player stat — how much the damage multiplier
    increases per +1 unit of that stat at current values.

    Because the formula is multiplicative across factors, the weight of a stat
    in one factor is scaled by the product of all other factors. Weights are
    directly comparable across stats for prioritising upgrades.
    """
    subs = _subs_map(player, target)
    return {name: float(expr.subs(subs)) for name, expr in _WEIGHT_EXPRS.items()}
