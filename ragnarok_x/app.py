import streamlit as st
from build_store import render_sidebar

st.set_page_config(page_title="Ragnarok X Tools", layout="centered")
render_sidebar()
st.title("Ragnarok X: Next Generation Tools")
st.markdown("""
Use the sidebar to navigate between tools.

- **Stat Conversion** — Convert raw stats to their advanced equivalents, compare stat options, and find how much more stat you need to hit a target.
- **Build Editor** — Create and edit builds with unified offensive and defensive stats.
- **DMG Calculator** — Select offensive and target builds to calculate damage output and compare multiple builds side by side.
- **Stat Optimization** — See effective multipliers per stat group and a ranked stat priority breakdown for your build vs a target.
- **Enchant Lookup** — Look up enchant stat values and quality probabilities by level, city, equipment, and stat.
""")