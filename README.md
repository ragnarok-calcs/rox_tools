# Ragnarok X: Next Generation Tools

A Streamlit web app for calculating and comparing in-game stats for **Ragnarok X: Next Generation**.

## Running the app

```bash
# Activate the virtual environment
source .venv/Scripts/activate   # Windows Git Bash

# Install dependencies
pip install -r requirements.txt

# Launch
cd ragnarok_x
streamlit run app.py
```

## Pages

### DMG Multiplier (`pages/2_DMG_Multiplier.py`)

The primary tool. Enter player and target stats to calculate an overall physical damage multiplier and a ranked breakdown of which stats yield the greatest return per point invested.

**Supports PVE and PVP modes**, each with their own formula and stat set.

**PVE formula**
```
(P.ATK × (Crit DMG Bonus − Crit DMG Reduc) + P.DMG Bonus × (1 + P.DMG Bonus%) − P.DMG Reduc)
× (1 + Final P.DMG Bonus − Final P.DMG Reduc)
× (Elemental Counter + Element Enhance)
× (1 + Bonus DMG to Element)
× (1 + Bonus DMG to Race)
× (1 + Final DMG Bonus − Final DMG Reduc)
× (Weapon Size Modifier + Size Enhance)
```

**PVP formula**
```
(8 × (above_inner_term) ^ 0.6 − PVP P.DMG Reduc)
× (1 + PVP Final P.DMG Bonus − PVP Final P.DMG Reduc)
+ PVP P.DMG Bonus
```
The PVP inner term additionally includes Size Reduction, Race Reduction, and Element Resist on the target side.

**Features**
- Inputs grouped by stat family (Base Attack, Crit, Size, Element, etc.) in collapsible expanders, each showing a live player/target net summary
- Percentage stats entered as integers (e.g. `150` = 1.5× crit multiplier); divided by 100 internally before formula evaluation
- Fixed-value stats (Weapon Size Modifier, Elemental Counter) use dropdown selectors
- Stat weights computed via `sympy` partial derivatives, scaled so all values represent change-per-1-unit-of-user-input for fair cross-stat comparison
- **Stat Priority** — horizontal bar chart with stats normalised to [0, 1]
- **Stat Equivalence** — progress-bar display showing how many points of every stat equal 1 point of the selected reference stat
- Build manager: save/load named player and target builds; export/import as JSON

### Stat Conversion (`pages/1_Stat_Conversion.py`) — currently disabled

Converts raw or %Final stats (ASPD, CRIT, CD Reduction, CT Reduction) to their advanced equivalents, compares stat options, and solves for how much more stat is needed to hit a target. Re-enable by removing the leading `_` from the filename.

## Architecture

```
ragnarok_x/
├── app.py                  # Streamlit landing page
├── pages/
│   ├── 2_DMG_Multiplier.py # Main damage calculator page
│   └── _1_Stat_Conversion.py  # Disabled stat conversion page
├── multiplier_stats/
│   ├── pve_multiplier.py   # PVE formula, dataclasses, sympy derivatives
│   └── pvp_multiplier.py   # PVP formula, dataclasses, sympy derivatives
├── stat_calculation/       # Stat conversion math (ASPD, CRIT, CD/CT Reduction)
├── dps_simulator/          # Jupyter notebook for rogue DPS simulation
└── refine_simulator/       # YAML data for weapon refinement (no entry point yet)
```

### Damage multiplier math

Both `pve_multiplier.py` and `pvp_multiplier.py` define their formula as a `sympy` symbolic expression at module level. Partial derivatives with respect to every player stat are computed once at import:

```python
_WEIGHT_EXPRS = {name: diff(_EXPR, sym) for name, sym in _PLAYER_SYMS.items()}
```

`modifier_weights(player, target)` substitutes current stat values into these pre-computed derivatives, returning a `dict[str, float]` of marginal weights.

The Streamlit page then scales weights for percentage fields by `0.01` so that all weights represent damage change per 1 unit of user-facing input (1 raw P.ATK vs 1% of Final DMG Bonus).
