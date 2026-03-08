# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Discord bot project for the game **Ragnarok X: Next Generation**. The bot exposes slash commands that help players calculate and compare in-game stats (ASPD, CRIT, CD Reduction, CT Reduction).

## Environment Setup

Uses Python 3.13 with a `.venv` virtual environment. Dependencies are in `requirements.txt`.

Key packages:
- `streamlit` — Web UI framework
- `sympy` — Symbolic math for stat formula solving
- `python-dotenv` — `.env` file loading
- `discord.py` — Retained for reference; the bot entrypoint is `app.py` (not the active app)

Activate the venv before running:
```bash
source .venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt
```

## Running the App

```bash
cd ragnarok_x
streamlit run app.py
```

## Running Tests

```bash
cd ragnarok_x
python -m pytest stat_calculation/test/
```

## Architecture

### `ragnarok_x/`
- **`streamlit_app.py`** — Main entry point. Four tabs: Convert Stat, Which is Better, How Much More, Stat Added.
- **`app.py`** — Original Discord bot (kept for reference; not the active app).
- **`stat_calculation/`** — Core stat math module.
- **`refine_simulator/`** — YAML data files for weapon refinement simulation (no Python entry point yet).
- **`dps_simulator/`** — Jupyter notebook for rogue DPS simulation.

### Stat Calculation Architecture

All stat classes inherit from `Stat` (in `STAT.py`), which uses `sympy` symbolic algebra to define a base equation:

```
raw_expr(raw) + final_expr(final) = stat
```

Each subclass (`ASPD`, `CRIT`, `CD_REDUC`, `CT_REDUC`) overrides `raw_expr` and `final_expr` with game-specific formulas, then overrides `base_eq` with the resulting `sympy.Eq`.

The `Stat` base class provides three public methods used by `app.py` commands:
- `convert_input(input_type, input_val)` — Convert raw or %Final stat to the advanced stat value.
- `compare_inputs(raw, final, current_raw, current_final)` — Compare what raw vs. %Final additions yield.
- `needed_input(current_raw, current_final, stat_to_quant, target_amt)` — Calculate how much more stat is needed to hit a target.

`stat_factory(stat_name)` in `__init__.py` maps string names (`'CRIT'`, `'ASPD'`, `'CT Reduction'`, `'CD Reduction'`) to instantiated stat objects.

### Adding a New Stat

1. Create a new class in `stat_calculation/` inheriting from `Stat`, define `name`, `raw_name`, `final_name`, `raw_expr`, `final_expr`, and `base_eq`.
2. Import and add it to `stat_factory()` in `stat_calculation/__init__.py`.
3. Add corresponding slash commands in `app.py`.

### Known Issues

- `PENETRATION.py` exists but is not wired into `stat_factory` or `app.py` yet.
- The `stat_added` command in `app.py` references undefined variable `target_stat` (should be `advanced_stat`) — it will fail at runtime.
- The `Stat` base class uses class-level `sympy` symbols, but subclasses call `super().__init__()` and set instance attributes — subclasses must use `self` (not `cls`) in their methods when instantiated.
- Test files under `stat_calculation/test/` are currently empty.