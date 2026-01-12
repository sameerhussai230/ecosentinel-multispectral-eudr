import os
import yaml
import json
import logging
import pystac_client
import planetary_computer
import stackstac
import rioxarray
import numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config():
    config_path = Path("config/settings.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

class SatelliteIngestor:
    def __init__(self, config):
        self.config = config
        self.catalog_url = "https://planetarycomputer.microsoft.com/api/stac/v1"
        self.raw_path = Path(config['paths']['raw_data'])
        self.raw_path.mkdir(parents=True, exist_ok=True)

    def _save_single_band(self, args):
        """Helper function for ThreadPool to save one file."""
        data, asset, file_path = args
        try:
            # clean old file
            if file_path.exists(): 
                file_path.unlink()
            
            # Select band, cast to float32 for efficiency, and save
            band_data = data.sel(band=asset).astype("float32")
            band_data.rio.to_raster(file_path)
            return f"Saved {asset}"
        except Exception as e:
            return f"Error saving {asset}: {e}"

    def search_and_download(self, override_bbox=None, override_date=None, override_name=None):
        try:
            catalog = pystac_client.Client.open(
                self.catalog_url,
                modifier=planetary_computer.sign_inplace
            )
            
            bbox = override_bbox if override_bbox else self.config['aoi']['bbox']
            date_range = override_date if override_date else self.config['satellite']['date_range']
            region_name = override_name if override_name else self.config['aoi']['name']
            
            logger.info(f"Tasking Satellite for: {region_name} | Range: {date_range}")

            # 1. Search
            search = catalog.search(
                collections=[self.config['satellite']['collection']],
                bbox=bbox,
                datetime=date_range,
                query={"eo:cloud_cover": {"lt": 25}}
            )
            
            items = search.item_collection()
            if not items:
                logger.warning("No images found.")
                return False
            
            selected_items = sorted(items, key=lambda x: x.properties['eo:cloud_cover'])[:5]
            logger.info(f"Found {len(selected_items)} scenes. Stacking...")

            # 2. Metadata
            primary_item = selected_items[0]
            metadata = {
                "region_name": region_name,
                "scene_id": "Mosaic_Composite",
                "acquisition_date": primary_item.datetime.isoformat(),
                "cloud_cover_avg": primary_item.properties['eo:cloud_cover'],
                "platform": primary_item.properties['platform'],
                "bbox": bbox
            }
            with open(self.raw_path / "metadata.json", "w") as f:
                json.dump(metadata, f, indent=4)

            # 3. Stack & Mosaic
            epsg_code = primary_item.properties.get("proj:epsg") or 32630
            assets = ["B02", "B03", "B04", "B08"]
            
            stack = stackstac.stack(
                selected_items,
                assets=assets,
                bounds_latlon=bbox,
                resolution=10,
                epsg=epsg_code
            )

            # Heavy Compute (Dask handles parallelism here internally)
            logger.info("Merging scenes (Median reduction)...")
            mosaic = stack.median(dim="time", keep_attrs=True)
            data = mosaic.compute()
            data = data.where(data > 0)

            # 4. PARALLEL SAVE (The Optimization)
            logger.info("Writing bands to disk in parallel...")
            
            # Prepare arguments for the worker threads
            tasks = []
            for asset in assets:
                file_path = self.raw_path / f"mosaic_{asset}.tif"
                tasks.append((data, asset, file_path))
            
            # Execute 4 writes simultaneously
            with ThreadPoolExecutor(max_workers=4) as executor:
                results = list(executor.map(self._save_single_band, tasks))
            
            for res in results:
                logger.info(res)
            
            return True

        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            raise

if __name__ == "__main__":
    conf = load_config()
    ingestor = SatelliteIngestor(conf)
    ingestor.search_and_download()