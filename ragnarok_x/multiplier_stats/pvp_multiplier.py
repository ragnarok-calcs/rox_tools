from dataclasses import dataclass
from sympy import symbols, diff, Rational

# ---------------------------------------------------------------------------
# Symbolic setup (module-level — derivatives computed once at import)
#
# Full formula:
#   (8 × (
#       (P.ATK × (Crit DMG Bonus - Target Crit DMG Reduc)
#        + P.DMG Bonus × (1 + P.DMG Bonus%) - Target P.DMG Reduc)
#       × (1 + Final P.DMG Bonus - Target Final P.DMG Reduc)
#       × (Weapon Size Modifier + Size Enhance)
#       × (1 + Bonus DMG to Race)
#       × (Elemental Counter + Element Enhance - Element Resist)
#       × (1 + Final DMG Bonus - Target Final DMG Reduc)
#   ) ^ 0.6 - Target PVP P.DMG Reduc)
#   × (1 + PVP Final P.DMG Bonus - Target PVP Final P.DMG Reduc)
#   + PVP P.DMG Bonus
# ---------------------------------------------------------------------------

# Player symbols
_PATK, _CRIT_BONUS, _PDMG_BONUS, _PDMG_BONUS_PCT = symbols(
    'patk crit_dmg_bonus pdmg_bonus pdmg_bonus_pct', positive=True
)
_FINAL_PDMG_BONUS, _ELEM_COUNTER, _ELEM_ENHANCE = symbols(
    'final_pdmg_bonus elemental_counter element_enhance', nonnegative=True
)
_FINAL_DMG_BONUS, _PVP_FINAL_PDMG_BONUS, _PVP_PDMG_BONUS = symbols(
    'final_dmg_bonus pvp_final_pdmg_bonus pvp_pdmg_bonus', nonnegative=True
)
_WEAPON_SIZE_MOD, _SIZE_ENHANCE, _BONUS_RACE = symbols(
    'weapon_size_modifier size_enhance bonus_dmg_race', nonnegative=True
)

# Target symbols
_CRIT_REDUC, _PDMG_REDUC, _FINAL_PDMG_REDUC = symbols(
    'crit_dmg_reduc pdmg_reduc final_pdmg_reduc', nonnegative=True
)
_ELEM_RESIST, _SIZE_REDUC, _RACE_REDUC, _FINAL_DMG_REDUC,  = symbols(
    'element_resist size_reduc race_reduc final_dmg_reduc', nonnegative=True
)
_PVP_PDMG_REDUC, _PVP_FINAL_PDMG_REDUC = symbols(
    'pvp_pdmg_reduc pvp_final_pdmg_reduc', nonnegative=True
)

_INNER = (
    (_PATK * (_CRIT_BONUS - _CRIT_REDUC)
     + _PDMG_BONUS * (1 + _PDMG_BONUS_PCT)
     - _PDMG_REDUC)
    * (1 + _FINAL_PDMG_BONUS - _FINAL_PDMG_REDUC)
    * (_WEAPON_SIZE_MOD + _SIZE_ENHANCE - _SIZE_REDUC)
    * (1 + _BONUS_RACE - _RACE_REDUC)
    * (_ELEM_COUNTER + _ELEM_ENHANCE - _ELEM_RESIST)
    * (1 + _FINAL_DMG_BONUS - _FINAL_DMG_REDUC)
)

_EXPR = (
    (8 * _INNER ** Rational(3, 5) - _PVP_PDMG_REDUC)
    * (1 + _PVP_FINAL_PDMG_BONUS - _PVP_FINAL_PDMG_REDUC)
    + _PVP_PDMG_BONUS
)

_PLAYER_SYMS = {
    'patk':                 _PATK,
    'crit_dmg_bonus':       _CRIT_BONUS,
    'pdmg_bonus':           _PDMG_BONUS,
    'pdmg_bonus_pct':       _PDMG_BONUS_PCT,
    'final_pdmg_bonus':     _FINAL_PDMG_BONUS,
    'weapon_size_modifier': _WEAPON_SIZE_MOD,
    'size_enhance':         _SIZE_ENHANCE,
    'bonus_dmg_race':       _BONUS_RACE,
    'elemental_counter':    _ELEM_COUNTER,
    'element_enhance':      _ELEM_ENHANCE,
    'final_dmg_bonus':      _FINAL_DMG_BONUS,
    'pvp_final_pdmg_bonus': _PVP_FINAL_PDMG_BONUS,
    'pvp_pdmg_bonus':       _PVP_PDMG_BONUS,
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
    weapon_size_modifier: float # Weapon Size Modifier (e.g. 1.0 base)
    size_enhance: float         # Size Enhance
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
# ---------------------------------------------------------------------------
def _subs_map(player: PlayerStats, target: TargetStats) -> dict:
    return {
        _PATK:                 player.patk,
        _CRIT_BONUS:           player.crit_dmg_bonus,
        _PDMG_BONUS:           player.pdmg_bonus,
        _PDMG_BONUS_PCT:       player.pdmg_bonus_pct,
        _FINAL_PDMG_BONUS:     player.final_pdmg_bonus,
        _WEAPON_SIZE_MOD:      player.weapon_size_modifier,
        _SIZE_ENHANCE:         player.size_enhance,
        _BONUS_RACE:           player.bonus_dmg_race,
        _ELEM_COUNTER:         player.elemental_counter,
        _ELEM_ENHANCE:         player.element_enhance,
        _FINAL_DMG_BONUS:      player.final_dmg_bonus,
        _PVP_FINAL_PDMG_BONUS: player.pvp_final_pdmg_bonus,
        _PVP_PDMG_BONUS:       player.pvp_pdmg_bonus,
        _CRIT_REDUC:           target.crit_dmg_reduc,
        _PDMG_REDUC:           target.pdmg_reduc,
        _FINAL_PDMG_REDUC:     target.final_pdmg_reduc,
        _ELEM_RESIST:          target.element_resist,
        _SIZE_REDUC:           target.size_reduc,
        _RACE_REDUC:           target.race_reduc,
        _FINAL_DMG_REDUC:      target.final_dmg_reduc,
        _PVP_PDMG_REDUC:       target.pvp_pdmg_reduc,
        _PVP_FINAL_PDMG_REDUC: target.pvp_final_pdmg_reduc,
    }


def calculate_multiplier(player: PlayerStats, target: TargetStats) -> float:
    """Return the overall PVP damage multiplier for the given player and target stats."""
    return float(_EXPR.subs(_subs_map(player, target)))


def modifier_weights(player: PlayerStats, target: TargetStats) -> dict[str, float]:
    """
    Return the marginal value of each player stat — how much the PVP damage
    multiplier increases per +1 unit of that stat at current values.

    Note: stats inside the ^0.6 term have diminishing returns — their weights
    decrease as those stats grow, unlike the outer PVP factors which scale linearly.
    """
    subs = _subs_map(player, target)
    return {name: float(expr.subs(subs)) for name, expr in _WEIGHT_EXPRS.items()}