import rasterio
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from pathlib import Path
import logging
import json
from concurrent.futures import ProcessPoolExecutor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def worker_generate_true_color(bands_paths, out_path):
    try:
        with rasterio.open(bands_paths["B04"]) as src_r, \
             rasterio.open(bands_paths["B03"]) as src_g, \
             rasterio.open(bands_paths["B02"]) as src_b:
            
            # Brighten image
            r = np.clip(src_r.read(1) / 2000.0, 0, 1)
            g = np.clip(src_g.read(1) / 2000.0, 0, 1)
            b = np.clip(src_b.read(1) / 2000.0, 0, 1)
            
            rgb = np.dstack((r, g, b))
            plt.imsave(out_path / "true_color.png", rgb)
            return "True Color Generated"
    except Exception as e:
        return f"RGB Error: {e}"

def worker_risk_analysis(bands_paths, out_path):
    try:
        with rasterio.open(bands_paths["B03"]) as src_g, \
             rasterio.open(bands_paths["B04"]) as src_r, \
             rasterio.open(bands_paths["B08"]) as src_n:
            
            green = src_g.read(1).astype('float32')
            red = src_r.read(1).astype('float32')
            nir = src_n.read(1).astype('float32')

            # --- 1. CALCULATE INDICES ---
            
            # NDVI (Vegetation)
            denom_ndvi = nir + red
            ndvi = np.full(green.shape, np.nan, dtype='float32')
            mask_ndvi = denom_ndvi > 0
            ndvi[mask_ndvi] = (nir[mask_ndvi] - red[mask_ndvi]) / denom_ndvi[mask_ndvi]

            # NDWI (Water)
            denom_ndwi = green + nir
            ndwi = np.full(green.shape, np.nan, dtype='float32')
            mask_ndwi = denom_ndwi > 0
            ndwi[mask_ndwi] = (green[mask_ndwi] - nir[mask_ndwi]) / denom_ndwi[mask_ndwi]

        # --- 2. CLASSIFICATION LOGIC ---
        
        non_veg_mask = (ndvi < 0.25) | (ndwi > 0.0)
        
        # Risk Threshold
        risk_threshold = 0.45
        risk_mask = (ndvi >= 0.25) & (ndvi < risk_threshold)
        healthy_mask = (ndvi >= risk_threshold)
        
        classification = np.zeros_like(ndvi)
        classification[healthy_mask] = 1
        classification[risk_mask] = 2
        # (non_veg is 0)

        # --- 3. SAVE IMAGES ---
        plt.figure(figsize=(10, 6))
        cmap = ListedColormap(['#d9d9d9', '#ffffff', '#ff3333'])
        plt.imshow(classification, cmap=cmap, interpolation='nearest', vmin=0, vmax=2)
        plt.axis('off')
        plt.savefig(out_path / "risk_mask.png", bbox_inches='tight', pad_inches=0)
        plt.close()

        plt.figure(figsize=(10, 6))
        plt.imshow(ndvi, cmap='RdYlGn', vmin=0, vmax=0.8)
        plt.axis('off')
        plt.savefig(out_path / "ndwi_spectrum.png", bbox_inches='tight', pad_inches=0)
        plt.close()

        # --- 4. STATISTICS (THE FIX) ---
        total_veg_pixels = np.sum(healthy_mask) + np.sum(risk_mask)
        stressed_pixels = np.sum(risk_mask)
        
        if total_veg_pixels > 0:
            stress_pct = float((stressed_pixels / total_veg_pixels) * 100)
        else:
            stress_pct = 0.0
            
        veg_coverage = float(total_veg_pixels / ndvi.size * 100)
        
        # FIXED: Changed threshold from 25 to 40 to match the App
        stats = {
            "stress_pct": round(stress_pct, 2),
            "threshold": risk_threshold,
            "status": "CRITICAL" if stress_pct > 40 else "COMPLIANT", 
            "vegetation_cover_pct": round(veg_coverage, 2)
        }
        with open(out_path / "stats.json", "w") as f:
            json.dump(stats, f)
            
        return "Smart Analysis Complete"
    except Exception as e:
        return f"Analysis Error: {e}"

class WaterStressAnalyzer:
    def __init__(self, raw_dir="data/raw", processed_dir="data/processed"):
        self.raw_path = Path(raw_dir)
        self.out_path = Path(processed_dir)
        self.out_path.mkdir(parents=True, exist_ok=True)

    def find_bands(self):
        return {
            "B02": self.raw_path / "mosaic_B02.tif",
            "B03": self.raw_path / "mosaic_B03.tif",
            "B04": self.raw_path / "mosaic_B04.tif",
            "B08": self.raw_path / "mosaic_B08.tif"
        }

    def run_parallel_pipeline(self):
        logger.info("Starting Parallel Pipeline...")
        bands_paths = self.find_bands()
        with ProcessPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(worker_generate_true_color, bands_paths, self.out_path)
            f2 = executor.submit(worker_risk_analysis, bands_paths, self.out_path)
            logger.info(f"Tasks: {f1.result()} | {f2.result()}")

if __name__ == "__main__":
    analyzer = WaterStressAnalyzer()
    analyzer.run_parallel_pipeline()