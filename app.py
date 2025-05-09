import streamlit as st
import requests
from datetime import datetime, timedelta

# --- WordPress Configuration ---
st.title("WordPress JWT Authentication")

# Configuration inputs
st.header("Server Configuration")
wp_url = st.text_input("WordPress Site URL", "https://yourwordpresssite.com")
api_key = st.text_input("API Key (from WordPress plugin)", type="password")

# User credentials
st.header("User Credentials")
username = st.text_input("Username")
password = st_text.input("Password", type="password")
token_expiry_hours = st.number_input("Token Expiry (hours)", 1, 720, 24)

def get_wp_jwt(username, password):
    """Retrieve JWT from WordPress REST API"""
    try:
        response = requests.post(
            f"{wp_url}/wp-json/jwt-auth/v1/token",
            data={'username': username, 'password': password},
            headers={'X-API-KEY': api_key}
        )
        if response.status_code == 200:
            return response.json().get('token')
        return None
    except Exception as e:
        st.error(f"Connection error: {str(e)}")
        return None

def verify_wp_token(token):
    """Validate JWT with WordPress server"""
    try:
        response = requests.post(
            f"{wp_url}/wp-json/jwt-auth/v1/token/validate",
            headers={
                'Authorization': f'Bearer {token}',
                'X-API-KEY': api_key
            }
        )
        return response.status_code == 200
    except:
        return False

# --- Token Generation Interface ---
st.header("Authentication")
if st.button("Generate WordPress Bearer Token"):
    if not all([wp_url, api_key, username, password]):
        st.warning("Please fill all required fields")
    else:
        with st.spinner("Authenticating with WordPress..."):
            jwt_token = get_wp_jwt(username, password)
            
            if jwt_token and verify_wp_token(jwt_token):
                st.success("Authentication Successful!")
                
                st.subheader("JWT Bearer Token")
                st.code(jwt_token)
                
                st.subheader("Usage Example")
                st.markdown(f"""
                ```
                import requests
                
                headers = {{
                    'Authorization': f'Bearer {jwt_token}',
                    'X-API-KEY': '{api_key}'
                }}
                
                response = requests.get(
                    '{wp_url}/wp-json/wp/v2/users/me',
                    headers=headers
                )
                ```
                """)
            else:
                st.error("Authentication Failed - Check credentials/configuration")

# --- Sidebar Information ---
st.sidebar.header("Configuration Notes")
st.sidebar.markdown("""
1. **Required WordPress Plugins**:
   - JWT Authentication for WP REST API (v1.3.2+)
   - Streamlit Integration Plugin (from [GitHub](https://github.com/Keyvanhardani/WordPress-Streamlit-Integration))

2. **Security Best Practices**:
   - Always use HTTPS
   - Rotate API keys regularly
   - Set appropriate token expiration times
   - Store secrets securely (consider `st.secrets` in production)
""")

st.sidebar.header("Troubleshooting")
st.sidebar.markdown("""
- Validate WordPress REST API endpoints first
- Check browser developer tools (Network tab)
- Verify plugin activation status
- Test with Postman/curl before Streamlit integration
""")
