import streamlit as st
import requests
from requests.auth import HTTPBasicAuth

st.title("WordPress Application Password Authentication")

# --- Configuration Inputs ---
st.header("WordPress Server Settings")
wp_url = st.text_input("WordPress Site URL", "https://yourwordpresssite.com")

# --- User Credentials ---
st.header("User Credentials")
username = st.text_input("Username (WordPress account)")
app_password = st.text_input("Application Password (from your WP Profile)", type="password")

# --- Function to Authenticate and Fetch User Info ---
def get_wp_user(wp_url, username, app_password):
    endpoint = f"{wp_url.rstrip('/')}/wp-json/wp/v2/users/me"
    try:
        response = requests.get(
            endpoint,
            auth=HTTPBasicAuth(username, app_password)
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        st.error(f"Connection error: {str(e)}")
        return None

# --- Authentication Button ---
if st.button("Authenticate and Fetch Profile"):
    if not all([wp_url, username, app_password]):
        st.warning("Please fill all the fields above.")
    else:
        with st.spinner("Authenticating with WordPress..."):
            user_info = get_wp_user(wp_url, username, app_password)
            if user_info:
                st.success("Authentication Successful!")
                st.subheader("Your WordPress User Profile:")
                st.json(user_info)
            else:
                st.error("Authentication failed. Check your credentials and site URL.")

# --- Sidebar Info ---
st.sidebar.header("Instructions")
st.sidebar.markdown("""
1. **Generate an Application Password** in your WordPress profile (Users > Profile > Application Passwords).
2. **Enter your site URL, username, and the generated app password** above.
3. **Click 'Authenticate and Fetch Profile'** to test the connection.

**Note:**  
- Your site must be HTTPS for Application Passwords to work.
- Application Passwords are different from your regular WP password.
- No plugin required for this method (WP 5.6+).
""")
