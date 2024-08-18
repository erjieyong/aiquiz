import streamlit as st

if "group" not in st.session_state:
    st.session_state.group = None

if st.session_state.group == None:
    # with st.form("setgroup"):
    #     groupname = st.text_input("Group Name: ", key="test")
    #     submitted = st.form_submit_button("Enter")

    # if submitted:
    #     st.session_state.group = groupname
    groupname = st.text_input("Group Name: ")

    if groupname:
        st.write(groupname)
        st.session_state.group = groupname
        st.rerun()


else:
    st.header(st.session_state.group)
    feedback = st.text_input("enter feedback", key="feeback")
    submitted = st.button("submit")

    if submitted:
        st.write(feedback)


st.session_state
