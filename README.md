# 🛰️ EcoSentinel: A Multi-Spectral Satellite Pipeline for Automated EUDR Compliance Auditing

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit)](https://streamlit.io/)
[![Sentinel-2](https://img.shields.io/badge/Data-Sentinel--2-green?style=for-the-badge)](https://planetarycomputer.microsoft.com/)
[![License](https://img.shields.io/badge/License-MIT-purple?style=for-the-badge)](LICENSE)

**EcoSentinel** is a high-performance geospatial engine designed to verify supply chain compliance with the **European Union Deforestation Regulation (EUDR)**. 

By leveraging the **Microsoft Planetary Computer API**, the system tasks the Sentinel-2 satellite constellation to retrieve real-time imagery, processes multi-spectral bands (NIR, Red, Green) in parallel, and generates an automated risk audit for any agricultural plot on Earth.

---

## 🚀 Key Capabilities

*   **Autonomous Tasking:** Automatically searches, filters (cloud cover < 25%), and downloads Sentinel-2 L2A imagery.
*   **Parallel Processing:** Uses `ThreadPoolExecutor` and `ProcessPoolExecutor` to handle heavy raster computations without UI lag.
*   **Smart Masking:** Implements a Multi-Index Decision Tree:
    *   **NDVI (Normalized Difference Vegetation Index):** Assesses plant health/chlorophyll.
    *   **NDWI (Normalized Difference Water Index):** Masks out water bodies to prevent false positives.
*   **Compliance Reports:** Generates dynamic HTML executive summaries classifying regions as "Compliant" or "Critical Risk" based on spectral stress analysis.

---

## 🕹️ Three Modes of Operation

EcoSentinel offers three distinct ways to target and audit land areas.

### 1. Preset Agricultural Hubs
Select from known high-risk or high-value regions (e.g., Amazon Rainforest, Bordeaux Vineyards) for instant analysis.

![Mode 1 Presets](gif/mode_1_preset.gif)

### 2. Global Geocoding Search
Type any address, city, or region name. The system geocodes the input and tasks the satellites for a 10km radius around that point.

![Mode 2 Search](gif/mode_2_search.gif)

### 3. Interactive Area Drawing
Use the polygon tool to draw a specific farm boundaries. Ideally suited for checking specific land parcels against EUDR plot data.

![Mode 3 Draw](gif/mode_3_draw.gif)

---

## 🛠️ Architecture

The pipeline consists of three decoupled modules:

1.  **`ingest.py`**: Connects to the STAC Catalog, filters for the least cloudy scenes in the requested time window, creates a cloud-free median mosaic, and saves raw bands (`B02`, `B03`, `B04`, `B08`) to disk.
2.  **`process.py`**: Reads raw bands to generate:
    *   **True Color Composite:** Human-readable visual verification.
    *   **Spectral Mask:** Calculates NDVI/NDWI and applies threshold logic (`0.25 < NDVI < 0.45` = Risk).
    *   **Statistics:** Computes vegetation cover percentage and stress percentage.
3.  **`app.py`**: A Streamlit frontend that orchestrates the pipeline, visualizes the data maps, and renders the compliance report.

---

## 📦 Installation & Setup

### Prerequisites
*   Python 3.9+
*   Git

### 1. Clone the Repository
```bash
git clone https://github.com/sameerhussai230/ecosentinel-multispectral-eudr.git
cd ecosentinel-multispectral-eudr
