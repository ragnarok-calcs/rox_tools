import streamlit as st
from build_store import render_sidebar

st.set_page_config(page_title="Ragnarok X Tools", layout="centered")
render_sidebar()
st.title("Ragnarok X: Next Generation Tools")
st.markdown("""
Use the sidebar to navigate between tools.

### 🔧 Tools
- **Enchant Lookup** — Look up enchant stat values and quality probabilities.

### ⚔️ Build Testing
- **Build Editor** — Create and edit offensive and defensive stats for builds.
- **⤷ Damage Calculator** — Use builds to calculate exact damage output and compare multiple builds.
- **⤷ Stat Optimizer** — Find stat priorities to guide build investment.
""")