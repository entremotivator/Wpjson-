import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import json
import os
import time
import base64
from datetime import datetime
import re
from urllib.parse import urlparse

# Set page configuration
st.set_page_config(
    page_title="WordPress to n8n Exporter",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main .block-container {padding-top: 2rem;}
    .stTabs [data-baseweb="tab-panel"] {padding-top: 1rem;}
    .success-box {
        background-color: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .warning-box {
        background-color: #fff3cd;
        color: #856404;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .error-box {
        background-color: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# App title and description
st.title("🔄 WordPress to n8n Exporter")
st.markdown("""
This tool helps you export WordPress content as n8n nodes and workflows.
Connect to your WordPress site, select what to export, and generate ready-to-use n8n components.
""")

# Create tabs for different functionality
tab1, tab2, tab3, tab4 = st.tabs(["Connection", "Export Options", "Advanced Settings", "Results"])

# --- Helper Functions ---
def test_connection(wp_url, auth):
    """Test the WordPress connection and API availability."""
    try:
        endpoint = f"{wp_url.rstrip('/')}/wp-json/wp/v2/types"
        resp = requests.get(endpoint, auth=auth, timeout=10)
        resp.raise_for_status()
        return True, "Connection successful! WordPress REST API is accessible."
    except requests.exceptions.ConnectionError:
        return False, "Connection error. Please check the WordPress URL."
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return False, "Authentication failed. Please check your username and application password."
        else:
            return False, f"HTTP Error: {e}"
    except Exception as e:
        return False, f"Error: {e}"

def get_custom_post_types(wp_url, auth):
    """Fetch all post types (including core types)."""
    endpoint = f"{wp_url.rstrip('/')}/wp-json/wp/v2/types"
    try:
        resp = requests.get(endpoint, auth=auth)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"Error fetching post types: {e}")
        return {}

def get_taxonomies(wp_url, auth):
    """Fetch all taxonomies."""
    endpoint = f"{wp_url.rstrip('/')}/wp-json/wp/v2/taxonomies"
    try:
        resp = requests.get(endpoint, auth=auth)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"Error fetching taxonomies: {e}")
        return {}

def fetch_all_posts(wp_url, post_type, auth, include_fields=None, max_items=None):
    """Fetch all posts for a given post type, handling pagination."""
    posts = []
    page = 1
    per_page = 100
    params = {'per_page': per_page, 'page': page}
    
    # Add fields parameter if specified
    if include_fields:
        params['_fields'] = ','.join(include_fields)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    while True:
        endpoint = f"{wp_url.rstrip('/')}/wp-json/wp/v2/{post_type}"
        status_text.text(f"Fetching {post_type} (page {page})...")
        
        try:
            resp = requests.get(endpoint, params=params, auth=auth, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            posts.extend(data)
            
            # Update progress
            progress_value = min(1.0, len(posts) / (max_items or 1000))
            progress_bar.progress(progress_value)
            
            # Check if we've reached the end or max items
            if len(data) < per_page or (max_items and len(posts) >= max_items):
                break
                
            page += 1
            
        except Exception as e:
            status_text.text(f"Error fetching {post_type} (page {page}): {e}")
            time.sleep(2)  # Wait before retrying
            retries = 3
            while retries > 0:
                try:
                    resp = requests.get(endpoint, params=params, auth=auth, timeout=30)
                    resp.raise_for_status()
                    data = resp.json()
                    posts.extend(data)
                    break
                except Exception:
                    retries -= 1
                    time.sleep(2)
            
            if retries == 0:
                status_text.text(f"Failed to fetch {post_type} after multiple retries")
                break
            
            page += 1
    
    progress_bar.empty()
    status_text.empty()
    
    # Limit to max_items if specified
    if max_items and len(posts) > max_items:
        posts = posts[:max_items]
        
    return posts

def fetch_taxonomy_terms(wp_url, taxonomy, auth, max_items=None):
    """Fetch all terms for a given taxonomy."""
    terms = []
    page = 1
    per_page = 100
    
    while True:
        endpoint = f"{wp_url.rstrip('/')}/wp-json/wp/v2/{taxonomy}"
        params = {'per_page': per_page, 'page': page}
        
        try:
            resp = requests.get(endpoint, params=params, auth=auth)
            resp.raise_for_status()
            data = resp.json()
            terms.extend(data)
            
            if len(data) < per_page or (max_items and len(terms) >= max_items):
                break
                
            page += 1
            
        except Exception as e:
            st.warning(f"Failed to fetch {taxonomy} terms (page {page}): {e}")
            break
    
    # Limit to max_items if specified
    if max_items and len(terms) > max_items:
        terms = terms[:max_items]
        
    return terms

def build_n8n_node(wp_url, username, app_password, endpoint, node_name, method="GET", pagination=True):
    """Build an n8n HTTP Request node."""
    node = {
        "parameters": {
            "authentication": "basicAuth",
            "url": f"{wp_url.rstrip('/')}/wp-json/wp/v2/{endpoint}",
            "method": method,
            "responseFormat": "json",
            "jsonParameters": True,
            "options": {},
            "sendQuery": True,
            "sendHeaders": True,
            "basicAuth": {
                "user": username,
                "password": app_password
            }
        },
        "name": node_name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 1,
        "position": [0, 0],
        "notesInFlow": False
    }
    
    # Add pagination handling if enabled
    if pagination and method == "GET":
        node["parameters"]["options"] = {
            "allowUnauthorizedCerts": False,
            "followRedirect": True,
            "ignoreResponseCode": False,
            "splitIntoItems": True,
            "timeout": 0,
            "redirect": {
                "redirect": {
                    "followRedirect": True
                }
            }
        }
        node["parameters"]["queryParametersJson"] = json.dumps({
            "per_page": 100,
            "page": "={{$parameter['page'] || 1}}"
        })
    
    return node

def build_n8n_workflow(nodes, name="WordPress Export Workflow"):
    """Build a complete n8n workflow with multiple nodes."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    workflow = {
        "name": name,
        "nodes": [],
        "connections": {},
        "active": False,
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
            "errorWorkflow": ""
        },
        "tags": ["wordpress", "export", "api"],
        "createdAt": now,
        "updatedAt": now,
        "id": f"wp-export-{int(time.time())}"
    }
    
    # Position nodes in a grid
    for i, node in enumerate(nodes):
        node_copy = node.copy()
        node_copy["position"] = [240 * (i % 3), 240 * (i // 3)]
        node_copy["id"] = f"node-{i+1}"
        workflow["nodes"].append(node_copy)
    
    return workflow

def save_n8n_node(node, filename, output_dir):
    """Save the n8n node as a JSON file."""
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(node, f, indent=2)
    return filepath

def sanitize_filename(name):
    """Convert a string to a valid filename."""
    return re.sub(r'[^\w\-\.]', '_', name)

def get_site_name(wp_url):
    """Extract a site name from the WordPress URL."""
    parsed = urlparse(wp_url)
    domain = parsed.netloc
    if domain.startswith('www.'):
        domain = domain[4:]
    return domain.split('.')[0]

# --- Connection Tab ---
with tab1:
    st.header("WordPress Connection")
    
    # Connection settings
    wp_url = st.text_input("WordPress Site URL", value="https://yourwordpresssite.com", 
                          help="The full URL to your WordPress site (e.g., https://example.com)")
    
    col1, col2 = st.columns(2)
    with col1:
        username = st.text_input("Username", help="Your WordPress username with administrator privileges")
    with col2:
        app_password = st.text_input("Application Password", type="password", 
                                    help="Generate this in WordPress under Users > Profile > Application Passwords")
    
    # Test connection button
    if st.button("Test Connection", type="primary"):
        if not all([wp_url, username, app_password]):
            st.warning("Please fill in all connection fields.")
        else:
            with st.spinner("Testing connection..."):
                auth = HTTPBasicAuth(username, app_password)
                success, message = test_connection(wp_url, auth)
                if success:
                    st.success(message)
                    # Store connection in session state
                    st.session_state['wp_connection'] = {
                        'url': wp_url,
                        'username': username,
                        'app_password': app_password,
                        'auth': auth
                    }
                    # Fetch and store post types and taxonomies
                    post_types = get_custom_post_types(wp_url, auth)
                    taxonomies = get_taxonomies(wp_url, auth)
                    st.session_state['post_types'] = post_types
                    st.session_state['taxonomies'] = taxonomies
                    
                    # Display summary
                    st.markdown(f"""
                    <div class="success-box">
                        <h3>Connection Summary</h3>
                        <p>Found {len(post_types)} post types and {len(taxonomies)} taxonomies.</p>
                        <p>You can now proceed to the Export Options tab.</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.error(message)

# --- Export Options Tab ---
with tab2:
    st.header("Export Options")
    
    if 'wp_connection' not in st.session_state:
        st.info("Please connect to your WordPress site in the Connection tab first.")
    else:
        # Output directory
        output_dir = st.text_input("Directory to save n8n files", 
                                  value="./n8n_export",
                                  help="Local directory where the n8n JSON files will be saved")
        
        # Export type selection
        export_type = st.radio(
            "What would you like to export?",
            ["Post Types", "Taxonomies", "Both", "Custom Endpoints"],
            horizontal=True
        )
        
        if export_type in ["Post Types", "Both"]:
            st.subheader("Post Types")
            
            # Get post types from session state
            post_types = st.session_state.get('post_types', {})
            
            if post_types:
                # Create a more user-friendly display of post types
                post_type_options = {}
                for slug, info in post_types.items():
                    post_type_options[slug] = f"{info.get('name', slug)} ({slug})"
                
                # Default selection: include standard post types and exclude system types
                default_selection = [slug for slug in post_types.keys() 
                                    if slug not in ['wp_block', 'wp_template', 'wp_template_part', 'wp_navigation']]
                
                selected_post_types = st.multiselect(
                    "Select post types to export",
                    options=list(post_type_options.keys()),
                    default=default_selection,
                    format_func=lambda x: post_type_options[x]
                )
                
                # Field selection
                st.markdown("##### Field Selection")
                field_selection = st.radio(
                    "Which fields to include",
                    ["All Fields", "Selected Fields"],
                    horizontal=True
                )
                
                selected_fields = None
                if field_selection == "Selected Fields":
                    common_fields = ["id", "title", "content", "excerpt", "date", "modified", 
                                    "slug", "status", "author", "featured_media"]
                    selected_fields = st.multiselect(
                        "Select fields to include",
                        options=common_fields,
                        default=["id", "title", "content", "slug", "status"]
                    )
                
                # Item limit
                max_items = st.number_input(
                    "Maximum items per post type (0 for all)",
                    min_value=0,
                    value=100,
                    help="Limit the number of items to export per post type. Set to 0 for unlimited."
                )
                max_items = None if max_items == 0 else max_items
                
            else:
                st.warning("No post types found. Please check your connection.")
        
        if export_type in ["Taxonomies", "Both"]:
            st.subheader("Taxonomies")
            
            # Get taxonomies from session state
            taxonomies = st.session_state.get('taxonomies', {})
            
            if taxonomies:
                # Create a more user-friendly display of taxonomies
                taxonomy_options = {}
                for slug, info in taxonomies.items():
                    taxonomy_options[slug] = f"{info.get('name', slug)} ({slug})"
                
                # Default selection: include standard taxonomies
                default_tax_selection = ["category", "post_tag"]
                default_tax_selection = [tax for tax in default_tax_selection if tax in taxonomies]
                
                selected_taxonomies = st.multiselect(
                    "Select taxonomies to export",
                    options=list(taxonomy_options.keys()),
                    default=default_tax_selection,
                    format_func=lambda x: taxonomy_options[x]
                )
                
                # Term limit
                max_terms = st.number_input(
                    "Maximum terms per taxonomy (0 for all)",
                    min_value=0,
                    value=100,
                    help="Limit the number of terms to export per taxonomy. Set to 0 for unlimited."
                )
                max_terms = None if max_terms == 0 else max_terms
                
            else:
                st.warning("No taxonomies found. Please check your connection.")
        
        if export_type == "Custom Endpoints":
            st.subheader("Custom Endpoints")
            
            # Custom endpoints input
            custom_endpoints = st.text_area(
                "Enter custom endpoints (one per line)",
                height=150,
                help="Enter custom WordPress REST API endpoints, one per line. Example: wp/v2/users"
            )
            
            custom_endpoint_list = [endpoint.strip() for endpoint in custom_endpoints.split('\n') if endpoint.strip()]
            
            # Method selection for each endpoint
            if custom_endpoint_list:
                st.markdown("##### HTTP Methods")
                endpoint_methods = {}
                
                for endpoint in custom_endpoint_list:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.text(endpoint)
                    with col2:
                        endpoint_methods[endpoint] = st.selectbox(
                            "Method",
                            options=["GET", "POST", "PUT", "DELETE"],
                            key=f"method_{endpoint}",
                            label_visibility="collapsed"
                        )

# --- Advanced Settings Tab ---
with tab3:
    st.header("Advanced Settings")
    
    if 'wp_connection' not in st.session_state:
        st.info("Please connect to your WordPress site in the Connection tab first.")
    else:
        # Export format
        st.subheader("Export Format")
        export_format = st.radio(
            "Export as",
            ["Individual Nodes", "Complete Workflow", "Both"],
            horizontal=True,
            help="Individual nodes can be imported one by one. Workflows contain multiple nodes arranged in a workflow."
        )
        
        # Workflow name (if applicable)
        if export_format in ["Complete Workflow", "Both"]:
            site_name = get_site_name(st.session_state['wp_connection']['url'])
            workflow_name = st.text_input(
                "Workflow Name",
                value=f"{site_name.capitalize()} Content Export",
                help="Name for the n8n workflow"
            )
        
        # Node settings
        st.subheader("Node Settings")
        
        # Pagination handling
        include_pagination = st.checkbox(
            "Include pagination parameters",
            value=True,
            help="Add pagination parameters to GET requests for handling large datasets"
        )
        
        # Error handling
        error_handling = st.checkbox(
            "Add error handling nodes",
            value=True,
            help="Add nodes to handle errors and retries"
        )
        
        # Authentication options
        st.subheader("Authentication")
        auth_method = st.radio(
            "Authentication Method",
            ["Basic Auth", "OAuth2 (if supported)", "API Key (if supported)"],
            horizontal=True,
            help="The authentication method to use in the n8n nodes"
        )
        
        # Include credentials in export
        include_credentials = st.checkbox(
            "Include credentials in export",
            value=True,
            help="If unchecked, credentials will be removed from the export and must be added manually in n8n"
        )
        
        # Additional options
        st.subheader("Additional Options")
        
        # Include sample data
        include_sample_data = st.checkbox(
            "Include sample data in nodes",
            value=True,
            help="Include a sample of the fetched data in the node export (useful for testing)"
        )
        
        # Sample data limit
        if include_sample_data:
            sample_data_limit = st.number_input(
                "Sample data items",
                min_value=1,
                max_value=50,
                value=5,
                help="Number of sample data items to include in each node"
            )
        
        # Create documentation
        create_docs = st.checkbox(
            "Generate documentation",
            value=True,
            help="Create a README file with instructions on how to use the exported nodes"
        )

# --- Export Button (outside tabs) ---
if 'wp_connection' in st.session_state:
    if st.button("Export to n8n", type="primary"):
        # Get connection details
        wp_conn = st.session_state['wp_connection']
        wp_url = wp_conn['url']
        username = wp_conn['username']
        app_password = wp_conn['app_password']
        auth = wp_conn['auth']
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize results storage
        exported_nodes = []
        exported_files = []
        
        with st.spinner("Exporting data..."):
            # Process post types
            if export_type in ["Post Types", "Both"]:
                post_types = st.session_state.get('post_types', {})
                
                for slug in selected_post_types:
                    info = post_types.get(slug, {})
                    rest_base = info.get('rest_base', slug)
                    
                    # Fetch posts
                    posts = fetch_all_posts(
                        wp_url, 
                        rest_base, 
                        auth, 
                        include_fields=selected_fields,
                        max_items=max_items
                    )
                    
                    # Build node
                    node_name = f"Fetch {info.get('name', slug)}"
                    node = build_n8n_node(
                        wp_url, 
                        username, 
                        app_password, 
                        rest_base, 
                        node_name,
                        pagination=include_pagination
                    )
                    
                    # Add sample data if requested
                    if include_sample_data and posts:
                        sample = posts[:min(len(posts), sample_data_limit)]
                        node["data"] = sample
                    
                    # Remove credentials if requested
                    if not include_credentials:
                        node["parameters"]["basicAuth"] = {"user": "", "password": ""}
                    
                    # Save node
                    if export_format in ["Individual Nodes", "Both"]:
                        filename = f"{sanitize_filename(slug)}_node.json"
                        filepath = save_n8n_node(node, filename, output_dir)
                        exported_files.append((slug, filepath, len(posts)))
                    
                    # Add to nodes list for workflow
                    exported_nodes.append(node)
            
            # Process taxonomies
            if export_type in ["Taxonomies", "Both"]:
                taxonomies = st.session_state.get('taxonomies', {})
                
                for slug in selected_taxonomies:
                    info = taxonomies.get(slug, {})
                    rest_base = info.get('rest_base', slug)
                    
                    # Fetch terms
                    terms = fetch_taxonomy_terms(
                        wp_url, 
                        rest_base, 
                        auth,
                        max_items=max_terms
                    )
                    
                    # Build node
                    node_name = f"Fetch {info.get('name', slug)} Terms"
                    node = build_n8n_node(
                        wp_url, 
                        username, 
                        app_password, 
                        rest_base, 
                        node_name,
                        pagination=include_pagination
                    )
                    
                    # Add sample data if requested
                    if include_sample_data and terms:
                        sample = terms[:min(len(terms), sample_data_limit)]
                        node["data"] = sample
                    
                    # Remove credentials if requested
                    if not include_credentials:
                        node["parameters"]["basicAuth"] = {"user": "", "password": ""}
                    
                    # Save node
                    if export_format in ["Individual Nodes", "Both"]:
                        filename = f"{sanitize_filename(slug)}_taxonomy_node.json"
                        filepath = save_n8n_node(node, filename, output_dir)
                        exported_files.append((f"{slug} (taxonomy)", filepath, len(terms)))
                    
                    # Add to nodes list for workflow
                    exported_nodes.append(node)
            
            # Process custom endpoints
            if export_type == "Custom Endpoints" and custom_endpoint_list:
                for endpoint in custom_endpoint_list:
                    method = endpoint_methods.get(endpoint, "GET")
                    
                    # Build node name from endpoint
                    endpoint_parts = endpoint.split('/')
                    node_name = f"{method} {endpoint_parts[-1].capitalize()}"
                    
                    # Build node
                    node = build_n8n_node(
                        wp_url, 
                        username, 
                        app_password, 
                        endpoint, 
                        node_name,
                        method=method,
                        pagination=(include_pagination and method == "GET")
                    )
                    
                    # Try to fetch sample data for GET requests
                    if include_sample_data and method == "GET":
                        try:
                            endpoint_url = f"{wp_url.rstrip('/')}/wp-json/{endpoint}"
                            resp = requests.get(endpoint_url, auth=auth, params={"per_page": sample_data_limit})
                            if resp.status_code == 200:
                                node["data"] = resp.json()
                        except Exception:
                            pass
                    
                    # Remove credentials if requested
                    if not include_credentials:
                        node["parameters"]["basicAuth"] = {"user": "", "password": ""}
                    
                    # Save node
                    if export_format in ["Individual Nodes", "Both"]:
                        filename = f"custom_{sanitize_filename(endpoint.replace('/', '_'))}_node.json"
                        filepath = save_n8n_node(node, filename, output_dir)
                        exported_files.append((endpoint, filepath, 0))
                    
                    # Add to nodes list for workflow
                    exported_nodes.append(node)
            
            # Create workflow if requested
            if export_format in ["Complete Workflow", "Both"] and exported_nodes:
                workflow = build_n8n_workflow(exported_nodes, name=workflow_name)
                
                # Save workflow
                workflow_filename = f"{sanitize_filename(workflow_name)}_workflow.json"
                workflow_path = save_n8n_node(workflow, workflow_filename, output_dir)
                exported_files.append(("Complete Workflow", workflow_path, len(exported_nodes)))
            
            # Create documentation if requested
            if create_docs and exported_files:
                readme_path = os.path.join(output_dir, "README.md")
                with open(readme_path, "w", encoding="utf-8") as f:
                    f.write(f"# WordPress to n8n Export\n\n")
                    f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write(f"WordPress Site: {wp_url}\n\n")
                    
                    f.write("## Exported Files\n\n")
                    for name, path, count in exported_files:
                        if "workflow" in path.lower():
                            f.write(f"- **{name}**: `{os.path.basename(path)}`\n")
                        else:
                            f.write(f"- **{name}**: `{os.path.basename(path)}` ({count} items)\n")
                    
                    f.write("\n## How to Use\n\n")
                    f.write("### Individual Nodes\n\n")
                    f.write("1. In n8n, open the workflow where you want to add the node\n")
                    f.write("2. Click on the hamburger menu (≡) in the top right\n")
                    f.write("3. Select 'Import from File'\n")
                    f.write("4. Choose the node JSON file you want to import\n")
                    f.write("5. The node will be added to your workflow\n")
                    
                    f.write("\n### Complete Workflow\n\n")
                    f.write("1. In n8n, go to the Workflows page\n")
                    f.write("2. Click on the 'Import from File' button\n")
                    f.write("3. Choose the workflow JSON file\n")
                    f.write("4. The complete workflow will be imported\n")
                    
                    if not include_credentials:
                        f.write("\n### Authentication\n\n")
                        f.write("The credentials have been removed from the exported files for security reasons. ")
                        f.write("You will need to add your WordPress credentials in n8n:\n\n")
                        f.write("1. Select each HTTP Request node\n")
                        f.write("2. In the node settings, go to 'Authentication'\n")
                        f.write("3. Select 'Basic Auth'\n")
                        f.write("4. Enter your WordPress username and application password\n")
                
                exported_files.append(("Documentation", readme_path, 0))
        
        # Switch to Results tab and show results
        tab4.header("Export Results")
        
        if exported_files:
            tab4.success(f"Successfully exported {len(exported_files)} files to {output_dir}")
            
            # Display exported files
            tab4.subheader("Exported Files")
            for name, filepath, count in exported_files:
                if "workflow" in filepath.lower():
                    tab4.markdown(f"- **{name}**: `{os.path.basename(filepath)}`")
                elif "README" in filepath:
                    tab4.markdown(f"- **{name}**: `{os.path.basename(filepath)}`")
                else:
                    tab4.markdown(f"- **{name}**: `{os.path.basename(filepath)}` ({count} items)")
            
            # Show sample of a node
            if exported_nodes:
                tab4.subheader("Sample Node Preview")
                tab4.json(exported_nodes[0])
        else:
            tab4.error("No files were exported. Please check your settings and try again.")

# --- Sidebar ---
st.sidebar.header("About")
st.sidebar.markdown("""
### WordPress to n8n Exporter

This tool helps you export WordPress content as n8n nodes and workflows for automation.

**Features:**
- Export post types, taxonomies, and custom endpoints
- Create individual nodes or complete workflows
- Include sample data for testing
- Configure pagination and authentication
- Generate documentation

**Version:** 2.0
""")

st.sidebar.header("Instructions")
st.sidebar.markdown("""
1. **Generate an Application Password** in your WordPress profile (Users > Profile > Application Passwords).
2. **Ensure your custom post types** are registered with `'show_in_rest' => true`.
3. **Enter your WordPress site URL, username, and app password** in the Connection tab.
4. **Select what to export** in the Export Options tab.
5. **Configure advanced settings** if needed.
6. **Click the export button** to generate n8n nodes and workflows.

**Note:**  
- Only post types and taxonomies with REST API support will be exported.
- Each file contains credentials for n8n's HTTP Basic Auth (handle securely).
- The app fetches all content for each type, handling pagination automatically.
""")

st.sidebar.header("Troubleshooting")
st.sidebar.markdown("""
**Common Issues:**

- **Connection Failed**: Check your WordPress URL and credentials.
- **No Post Types Found**: Ensure your WordPress REST API is enabled.
- **Export Empty**: Check if your post types have the 'show_in_rest' parameter set to true.
- **Authentication Error**: Regenerate your application password in WordPress.

For more help, check the [WordPress REST API Documentation](https://developer.wordpress.org/rest-api/).
""")
