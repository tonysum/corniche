import streamlit as st
from binance_api import get_top3_gainers
if st.button("This is the Top 3 selection page."):
    df = get_top3_gainers()
    st.dataframe(df)