import rasterio
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# 1. Find the file automatically
data_dir = Path("data/raw")
# Grab the first .tif file found in the folder
file_path = list(data_dir.glob("*_B03.tif"))[0] 

print(f"Inspecting file: {file_path}")

# 2. Open using Rasterio
with rasterio.open(file_path) as src:
    print(f"Image Size: {src.width}x{src.height}")
    print(f"Coordinate System: {src.crs}")
    
    # Read the data (Band 1)
    img = src.read(1)

    # 3. Normalize for Display (Sentinel-2 Hack)
    # Raw values are 0-10000+. We scale them down to 0-1 for the screen.
    # We divide by 3000 because vegetation usually reflects < 3000 units.
    img_display = img / 3000.0
    img_display = np.clip(img_display, 0, 1) # Clip anything too bright

    # 4. Plot
    plt.figure(figsize=(10, 10))
    plt.imshow(img_display, cmap='gray')
    plt.title(f"QA Check: Green Band (B03)\n{file_path.name}")
    plt.colorbar(label="Reflectance (Scaled)")
    plt.axis('off') # Hide axis numbers
    plt.show()