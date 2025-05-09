import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import json
import os

st.title("Export WordPress Custom Post Types as n8n JSON Nodes")

# --- User Inputs ---
st.header("WordPress Credentials & Settings")
wp_url = st.text_input("WordPress Site URL", "https://yourwordpresssite.com")
username = st.text_input("Username (WordPress account)")
app_password = st.text_input("Application Password", type="password")
output_dir = st.text_input("Directory to save n8n node JSON files", "./n8n_nodes")

# --- Helper Functions ---

def get_custom_post_types(wp_url, auth):
    """Fetch all custom post types (excluding core types)."""
    endpoint = f"{wp_url.rstrip('/')}/wp-json/wp/v2/types"
    try:
        resp = requests.get(endpoint, auth=auth)
        resp.raise_for_status()
        all_types = resp.json()
        # Exclude core types (post, page, attachment, nav_menu_item, etc.)
        custom_types = {
            k: v for k, v in all_types.items()
            if v.get('slug') not in ['post', 'page', 'attachment', 'nav_menu_item', 'wp_block']
            and v.get('rest_base')
        }
        # Also include 'post' and 'page' for completeness
        for k in ['post', 'page']:
            if k in all_types:
                custom_types[k] = all_types[k]
        return custom_types
    except Exception as e:
        st.error(f"Error fetching post types: {e}")
        return {}

def fetch_all_posts(wp_url, post_type, auth):
    """Fetch all posts for a given post type, handling pagination."""
    posts = []
    page = 1
    per_page = 100
    while True:
        endpoint = f"{wp_url.rstrip('/')}/wp-json/wp/v2/{post_type}"
        params = {'per_page': per_page, 'page': page}
        resp = requests.get(endpoint, params=params, auth=auth)
        if resp.status_code == 200:
            data = resp.json()
            posts.extend(data)
            if len(data) < per_page:
                break
            page += 1
        else:
            st.warning(f"Failed to fetch {post_type} (page {page}): {resp.text}")
            break
    return posts

def build_n8n_node(wp_url, username, app_password, post_type, posts):
    """Build an n8n HTTP Request node for a given post type."""
    return {
        "parameters": {
            "authentication": "basicAuth",
            "url": f"{wp_url.rstrip('/')}/wp-json/wp/v2/{post_type}",
            "method": "GET",
            "responseFormat": "json",
            "jsonParameters": True,
            "options": {},
            "queryParametersJson": "{}",
            "headerParametersJson": "{}",
            "sendQuery": True,
            "sendHeaders": True,
            "basicAuth": {
                "user": username,
                "password": app_password
            }
        },
        "name": f"Fetch {post_type}",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 1,
        "position": [0, 0],
        "notesInFlow": False,
        "data": posts
    }

def save_n8n_node(node, post_type, output_dir):
    """Save the n8n node as a JSON file."""
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"{post_type}_n8n_node.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(node, f, indent=2)
    return filename

# --- Main Logic ---

if st.button("Export All Custom Post Types as n8n Nodes"):
    if not all([wp_url, username, app_password, output_dir]):
        st.warning("Please fill all fields above.")
    else:
        with st.spinner("Fetching custom post types..."):
            auth = HTTPBasicAuth(username, app_password)
            custom_types = get_custom_post_types(wp_url, auth)
            if not custom_types:
                st.error("No custom post types found or authentication failed.")
            else:
                st.success(f"Found post types: {', '.join(custom_types.keys())}")
                exported = []
                for slug, info in custom_types.items():
                    st.write(f"Fetching posts for: **{slug}**")
                    posts = fetch_all_posts(wp_url, info['rest_base'], auth)
                    node = build_n8n_node(wp_url, username, app_password, info['rest_base'], posts)
                    filename = save_n8n_node(node, slug, output_dir)
                    exported.append((slug, filename, len(posts)))
                st.success("Export complete!")
                for slug, filename, count in exported:
                    st.markdown(f"- `{slug}`: {count} posts exported to `{filename}`")

# --- Sidebar Instructions ---
st.sidebar.header("Instructions")
st.sidebar.markdown("""
1. **Generate an Application Password** in your WordPress profile (Users > Profile > Application Passwords).
2. **Ensure your custom post types** are registered with `'show_in_rest' => true`.
3. **Enter your WordPress site URL, username, and app password** above.
4. **Click the export button** to save each post type's data as an n8n HTTP Request node JSON file.
5. **Import the JSON files into n8n** as nodes for further workflow automation.

**Note:**  
- Only post types with REST API support will be exported.
- Each file contains credentials for n8n's HTTP Basic Auth (handle securely).
- The app fetches all posts for each type, handling pagination automatically.
""")
