import streamlit as st

st.set_page_config(
    page_title="AI RFP Excel Generator",
    page_icon="📊",
    layout="wide",
)

st.title("AI RFP Excel Generator")
st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Upload Reference PDF")
    pdf_file = st.file_uploader("Choose a PDF file", type=["pdf"], key="pdf_uploader")

with col2:
    st.subheader("Upload Excel Template")
    excel_file = st.file_uploader("Choose an Excel file", type=["xlsx", "xls"], key="excel_uploader")

if pdf_file and excel_file:
    st.success("Both files uploaded successfully!")
    if st.button("Analyze Files", type="primary"):
        st.info("Analysis will be implemented in future work items.")
