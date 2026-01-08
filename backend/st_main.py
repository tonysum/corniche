import streamlit as st

top3_page = st.Page("st_top3.py", title="U本位合约前三", icon=":material/add_task:")
low3_page = st.Page("st_low3.py", title="Select Low 3", icon=":material/delete:")

pg = st.navigation([top3_page, low3_page])
st.set_page_config(page_title="Data manager", page_icon=":material/edit:")
pg.run()