import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
from stat_calculation import stat_factory

st.set_page_config(page_title="Stat Conversion", layout="centered")
st.title("Stat Conversion")

STAT_OPTIONS = ['ASPD', 'CRIT', 'CD Reduction', 'CT Reduction']

tab1, tab2, tab3, tab4 = st.tabs(["Convert Stat", "Which is Better", "How Much More", "Stat Added"])

with tab1:
    st.subheader("Convert Stat")
    st.caption("Convert a raw or %Final stat into its advanced stat value.")

    stat_choice = st.selectbox("Stat", STAT_OPTIONS, key="c_stat")

    if stat_choice in ('CD Reduction', 'CT Reduction'):
        input_label = st.selectbox("Input type", ["Haste", "%Final Haste"], key="c_haste_type")
        input_type = 'raw' if input_label == "Haste" else 'final'
    else:
        input_type = 'raw'

    amount = st.number_input("Amount", value=0.0, min_value=0.0, key="c_amount")

    if st.button("Calculate", key="c_btn"):
        stat_cls = stat_factory(stat_choice)
        result = stat_cls.convert_input(input_type=input_type, input_val=amount)
        st.success(result)

with tab2:
    st.subheader("Which is Better?")
    st.caption("Compare adding raw stat vs. %Final stat to see which yields more.")

    stat_choice = st.selectbox("Stat", STAT_OPTIONS, key="wib_stat")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Current**")
        current_raw = st.number_input("Current Raw", value=0, min_value=0, step=1, key="wib_cur_raw")
        current_final = st.number_input("Current %Final", value=0.0, min_value=0.0, key="wib_cur_final")
    with col2:
        st.markdown("**Amount to Add**")
        raw_added = st.number_input("Raw to Add", value=0, min_value=0, step=1, key="wib_raw_add")
        final_added = st.number_input("%Final to Add", value=0.0, min_value=0.0, key="wib_final_add")

    if st.button("Compare", key="wib_btn"):
        stat_cls = stat_factory(stat_choice)
        name, current_solve, raw_solve, final_solve = stat_cls.compare_inputs(
            raw=raw_added, final=final_added,
            current_raw=current_raw, current_final=current_final
        )
        current_val = float(current_solve)
        raw_val = float(raw_solve)
        final_val = float(final_solve)

        st.metric("Current", f"{current_val:.2f} {name}")
        c1, c2 = st.columns(2)
        c1.metric(f"+ {raw_added} Raw", f"{raw_val:.2f} {name}",
                  delta=f"+{raw_val - current_val:.2f}")
        c2.metric(f"+ {final_added} %Final", f"{final_val:.2f} {name}",
                  delta=f"+{final_val - current_val:.2f}")

with tab3:
    st.subheader("How Much More?")
    st.caption("How much raw or %Final stat do you need to reach a target?")

    stat_choice = st.selectbox("Stat", STAT_OPTIONS, key="hmm_stat")
    col1, col2 = st.columns(2)
    with col1:
        current_raw = st.number_input("Current Raw", value=0, min_value=0, step=1, key="hmm_cur_raw")
        current_final = st.number_input("Current %Final", value=0.0, min_value=0.0, key="hmm_cur_final")
    with col2:
        target_amount = st.number_input("Target Amount", value=0.0, key="hmm_target")
        stat_type = st.selectbox("Solve for", ["raw", "final"], key="hmm_type")

    if st.button("Calculate", key="hmm_btn"):
        stat_cls = stat_factory(stat_choice)
        name, target_amt, stat_needed, _, needed_name = stat_cls.needed_input(
            current_raw=current_raw, current_final=current_final,
            stat_to_quant=stat_type, target_amt=target_amount
        )
        st.success(f"To reach **{target_amt} {name}**, you need **{float(stat_needed):.2f}** more {needed_name}.")

with tab4:
    st.subheader("Stat Added")
    st.caption("How much does adding a base stat change your advanced stat?")

    stat_choice = st.selectbox("Advanced Stat", STAT_OPTIONS, key="sa_stat")
    base_stat_type = st.selectbox("Base stat type", ["raw", "final"], key="sa_type")
    col1, col2 = st.columns(2)
    with col1:
        current_base = st.number_input("Current Base Stat", value=0.0, min_value=0.0, key="sa_current")
    with col2:
        added_base = st.number_input("Base Stat to Add", value=0.0, min_value=0.0, key="sa_added")

    if st.button("Calculate", key="sa_btn"):
        stat_cls = stat_factory(stat_choice)
        if base_stat_type == 'raw':
            current_raw, current_final = int(current_base), 0.0
            raw_added, final_added = int(added_base), 0.0
        else:
            current_raw, current_final = 0, current_base
            raw_added, final_added = 0, added_base

        name, current_solve, raw_solve, final_solve = stat_cls.compare_inputs(
            raw=raw_added, final=final_added,
            current_raw=current_raw, current_final=current_final
        )
        if base_stat_type == 'raw':
            gained = float(raw_solve - current_solve)
        else:
            gained = float(final_solve - current_solve)

        st.success(f"Adding **{added_base} {base_stat_type}** stat increases **{name}** by **{gained:.2f}**.")