import streamlit as st
from pathlib import Path
from PIL import Image
import yaml
import json
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from ingest import SatelliteIngestor
from process import WaterStressAnalyzer

st.set_page_config(page_title="EcoSentinel | EUDR", page_icon="🌍", layout="wide")

# --- HELPER 1: CSS Styling ---
def styled_caption(text):
    st.markdown(f"<p style='text-align: center; font-size: 110%; color: #666; font-style: italic;'>{text}</p>", unsafe_allow_html=True)

# --- HELPER 2: Robust HTML Generator (Dynamic Text Logic) ---
def generate_audit_html(pct, veg_pct):
    """
    Constructs HTML line-by-line with dynamic reasoning based on risk levels.
    """
    # 1. Determine Logic & Text
    if pct > 40:
        # Critical Scenario
        status_color = "#ffe6e6" # Red tint
        border_color = "#ff0000" # Red border
        tone = "Critical Risk"
        stress_desc = '<span style="color: #d32f2f; font-weight: bold;">critical spectral stress</span> (Red Zones)'
        action = "This indicates potential deforestation or severe drought. Immediate on-site audit recommended."
    else:
        # Compliant Scenario
        status_color = "#e6ffe6" # Green tint
        border_color = "#008000" # Green border
        tone = "Compliant"
        stress_desc = '<span style="color: #d32f2f; font-weight: bold;">moderate spectral variation</span> (typical for this biome)'
        action = "Vegetation gaps are within standard agricultural or forestry tolerance (thinning/spacing)."

    # 2. Build HTML List (Zero Indentation Guaranteed)
    html_lines = [
        f'<div style="background-color: {status_color}; padding: 20px; border-left: 6px solid {border_color}; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-top: 20px;">',
        f'<h3 style="margin-top:0; color: #333; font-family: sans-serif;">🛡️ Executive Summary: {pct}% Risk ({tone})</h3>',
        '<p style="font-size: 16px; line-height: 1.6; color: #444;">',
        '<strong>Risk Assessment:</strong><br>',
        f'The algorithm has identified that <b>{pct}%</b> of the agricultural vegetation in this sector is exhibiting ',
        f'{stress_desc}. ',
        f'{action}',
        '</p>',
        '<div style="background-color: rgba(255,255,255,0.6); padding: 15px; border-radius: 5px; margin-top: 15px;">',
        '<strong>🔬 Algorithmic Methodology (Multi-Index Decision Tree):</strong>',
        '<ul style="margin-top: 5px; color: #555;">',
        '<li><span style="color: #0277bd; font-weight: bold;">🔵 BLUE (Water):</span> Masked via NDWI > 0 (Surface water bodies).</li>',
        '<li><span style="color: #757575; font-weight: bold;">⚪ GREY (Urban/Barren):</span> Excluded where NDVI < 0.25 (Non-organic surfaces).</li>',
        '<li><span style="color: #d32f2f; font-weight: bold;">🔴 RED (Risk):</span> Vegetation with NDVI 0.25–0.45 (Sparse/Stressed signal).</li>',
        '<li><span style="color: #2e7d32; font-weight: bold;">⚪ WHITE (Safe):</span> Vegetation with NDVI > 0.45 (Dense chlorophyll signal).</li>',
        '</ul>',
        '</div>',
        '<hr style="border-top: 1px solid #ccc; margin: 15px 0;">',
        '<small style="color: #666;">',
        f'<em>Data Validity Check: This analysis detected active vegetation cover of <b>{veg_pct}%</b>. ',
        '(Areas with < 10% cover may indicate invalid seasonal windows or desert terrain).</em>',
        '</small>',
        '</div>'
    ]
    
    return "".join(html_lines)

# --- HELPER 3: Geocoding ---
def get_coordinates(place_name):
    geolocator = Nominatim(user_agent="ecosentinel_app")
    try:
        location = geolocator.geocode(place_name)
        if location:
            lat, lon = location.latitude, location.longitude
            return [lon - 0.05, lat - 0.05, lon + 0.05, lat + 0.05], f"{location.address}"
        return None, None
    except:
        return None, None

# --- CONFIG & PRESETS ---
PRESETS = {
    "Bordeaux, France (Vineyards)": [-0.60, 44.80, -0.50, 44.90],
    "Jaén, Spain (Olive Groves)": [-3.70, 37.80, -3.60, 37.90],
    "Berlin, Germany (Tesla Factory)": [13.78, 52.38, 13.82, 52.42],
    "Lombardy, Italy (Rice Fields)": [9.10, 45.40, 9.20, 45.50],
    "Amazon Rainforest (Deforestation)": [-62.20, -9.60, -62.10, -9.50]
}

def load_config():
    with open("config/settings.yaml", "r") as f: return yaml.safe_load(f)

def load_data():
    data = {"meta": {}, "stats": {}}
    if Path("data/raw/metadata.json").exists():
        with open("data/raw/metadata.json") as f: data["meta"] = json.load(f)
    if Path("data/processed/stats.json").exists():
        with open("data/processed/stats.json") as f: data["stats"] = json.load(f)
    return data

config = load_config()
data = load_data()
meta = data["meta"]
stats = data["stats"]

# --- SIDEBAR CONTROL PANEL ---
st.sidebar.title("EcoSentinel 🛰️")
st.sidebar.header("🗓️ Select Region & Date")

mode = st.sidebar.radio("Targeting Mode", ["Use Presets", "Search Anywhere 🌍", "Draw Area ✏️"])

bbox = None
region_name = "Unknown"

if mode == "Use Presets":
    selected_preset = st.sidebar.selectbox("Choose Region", list(PRESETS.keys()))
    bbox = PRESETS[selected_preset]
    region_name = selected_preset

elif mode == "Search Anywhere 🌍":
    custom_loc = st.sidebar.text_input("Enter Location", placeholder="e.g. Kyoto, Japan")
    st.sidebar.caption("System will analyze a 10km radius.")
    if custom_loc:
        found_bbox, found_address = get_coordinates(custom_loc)
        if found_bbox:
            bbox = found_bbox
            region_name = found_address
            st.sidebar.success("✅ Coordinates Found")
        else:
            st.sidebar.warning("❌ Location not found.")

elif mode == "Draw Area ✏️":
    st.sidebar.info("Use the drawing tools on the 'Location' map.")
    region_name = "Custom Drawing"

today = datetime.now()
date_input = st.sidebar.date_input("Search Window", value=(today - timedelta(days=60), today))

run_clicked = st.sidebar.button("🚀 Run Analysis", type="primary")

# --- MAIN UI ---
st.title(f"🌍 EUDR Multi-Spectral Deforestation Engine")

# --- PROJECT DESCRIPTION ---
with st.expander("ℹ️ About the Platform & Methodology", expanded=True):
    st.markdown("""
    **Objective:** This platform provides real-time, satellite-based auditing for the **EU Deforestation Regulation (EUDR)**. 
    It enables supply chain managers and financial auditors to verify if a sourcing region complies with environmental standards.
    
    **How it works:**
    1.  **Ingestion:** Tasks the **Sentinel-2 constellation** (via Microsoft Planetary Computer) to retrieve multi-spectral imagery.
    2.  **Processing:** Applies a parallelized Python pipeline to calculate **NDVI** (Vegetation Health) and **NDWI** (Water Content).
    3.  **Smart Masking:** Uses a Multi-Index Decision Tree to filter out urban noise and water bodies.
    4.  **Audit:** Generates a precise "Risk Score" based on vegetation stress levels.
    """)

st.markdown(f"### **Target:** {meta.get('region_name', region_name)}")

tab1, tab2, tab3 = st.tabs(["🗺️ Location & Targeting", "👁️ Multi-Spectral Detection", "📊 Compliance Audit"])

with tab1:
    if mode == "Draw Area ✏️":
        st.subheader("Interactive Targeting Map")
        start_loc = [48.85, 2.35]
        m = folium.Map(location=start_loc, zoom_start=5)
        draw = Draw(export=False, position='topleft', draw_options={'polyline':False,'polygon':False,'circle':False,'marker':False,'circlemarker':False,'rectangle':True})
        draw.add_to(m)
        output = st_folium(m, width=1400, height=500)
        
        if output and output['last_active_drawing']:
            coords = output['last_active_drawing']['geometry']['coordinates'][0]
            lons = [p[0] for p in coords]
            lats = [p[1] for p in coords]
            bbox = [min(lons), min(lats), max(lons), max(lats)]
            st.success(f"✅ Area Captured: {bbox}")
            region_name = "Custom User Selection"
            
    else:
        map_bbox = meta.get('bbox', bbox)
        if map_bbox:
            center = [(map_bbox[1]+map_bbox[3])/2, (map_bbox[0]+map_bbox[2])/2]
            m = folium.Map(location=center, zoom_start=11)
            folium.Rectangle([[map_bbox[1], map_bbox[0]], [map_bbox[3], map_bbox[2]]], color="red", fill=True, fill_opacity=0.1).add_to(m)
            folium.Marker(center, icon=folium.Icon(color="blue", icon="info-sign"), popup=region_name).add_to(m)
            st_folium(m, width=1400, height=400)
        else:
            st.info("Select a Preset or Search to view map.")

if run_clicked:
    if not bbox:
        st.error("⚠️ No Area Selected!")
    else:
        with st.status("Initializing Autonomous Pipeline...", expanded=True) as status:
            if isinstance(date_input, tuple) and len(date_input) == 2:
                dr = f"{date_input[0].strftime('%Y-%m-%d')}/{date_input[1].strftime('%Y-%m-%d')}"
            else:
                st.error("Invalid Date Range")
                st.stop()

            status.write(f"🛰️ Tasking Constellation for: {region_name}")
            ingestor = SatelliteIngestor(config)
            success = ingestor.search_and_download(override_bbox=bbox, override_date=dr, override_name=region_name)
            
            if not success:
                st.error("Mission Failed: No cloud-free images found.")
                st.stop()

            status.write("🧠 Computing Multi-Spectral Models (Parallel)...")
            analyzer = WaterStressAnalyzer()
            analyzer.run_parallel_pipeline()
            
            status.update(label="Complete", state="complete")
            st.rerun()

# --- TAB 2: VISUAL INSPECTION ---
with tab2:
    if meta:
        # --- ROW 1: INPUT DATA ---
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Optical Reality")
            if Path("data/processed/true_color.png").exists():
                st.image("data/processed/true_color.png", use_container_width=True)
                styled_caption("Sentinel-2 Composite (Visible Light)")

        with col2:
            st.subheader("Multi-Spectral Deforestation Detection")
            if Path("data/processed/ndwi_spectrum.png").exists():
                st.image("data/processed/ndwi_spectrum.png", use_container_width=True)
                styled_caption("Hybrid Spectral Analysis (NDVI + NDWI)")

        st.divider()

        # --- ROW 2: OUTPUT RESULT ---
        st.subheader("Multi-Class Masking & Compliance Map")
        
        if Path("data/processed/risk_mask.png").exists():
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2:
                st.image("data/processed/risk_mask.png", use_container_width=True)
                styled_caption("EUDR Classification Layer")

            # --- DETAILED EXPLANATION BOX (Dynamic Text) ---
            pct = stats.get('stress_pct', 0)
            veg_pct = stats.get('vegetation_cover_pct', 0)
            
            # Generate the HTML safely using the helper function
            html_report = generate_audit_html(pct, veg_pct)
            st.markdown(html_report, unsafe_allow_html=True)
            
    else:
        st.info("Awaiting tasking.")

# --- TAB 3: METRICS ---
with tab3:
    if stats:
        c1, c2, c3 = st.columns(3)
        pct = stats['stress_pct']
        # Ensures Tab 3 always matches Tab 2, regardless of what's in the JSON
        status_text = "CRITICAL" if pct > 40 else "COMPLIANT"
        
        c1.metric("Stress Area", f"{pct}%")
        c2.metric("Compliance", status_text) # Uses Dynamic Variable
        c3.metric("Cloud Cover", f"{meta.get('cloud_cover_avg', 0):.1f}%")
        st.json(meta)