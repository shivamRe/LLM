def test_connection():
    st.write("Step 1")

    try:
        st.write("Step 2")

        conn = get_connection()

        st.write("Step 3")

        with conn.cursor() as cursor:
            st.write("Step 4")
            cursor.execute("SELECT 1")
            st.write("Step 5")
            cursor.fetchall()

        st.success("Connected")
        return True

    except Exception as e:
        st.exception(e)
        return False
