import os
import shutil
from tqdm import tqdm

# --- CONFIGURATION ---
YOLO_MASTER_DIR = r"D:\RAJU\rs\IssacSim\rockynotes_master_yolo_2640"
STATIC_RAW_DIR = r"D:\RAJU\rs\IssacSim\rockynotes_dataset_final"
DRONE_RAW_DIR = r"D:\RAJU\rs\IssacSim\rockynotes_drone_raw"

OUTPUT_DIR = r"D:\RAJU\rs\IssacSim\rockynotes_multimodal_2640"

# The 5 data modalities we want to extract
MODALITIES = [
    "rgb", 
    "bounding_box_2d_tight", 
    "instance_segmentation", 
    "semantic_segmentation", 
    "distance_to_camera"
]

print("\n" + "="*60)
print("📦 ROCKYNOTES MULTI-MODAL DATASET EXTRACTOR 📦")
print("="*60)

# 1. Build the robust Output Directory Structure
if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)

for split in ['train', 'val']:
    for mod in MODALITIES:
        os.makedirs(os.path.join(OUTPUT_DIR, split, mod), exist_ok=True)

missing_files = 0
copied_files = 0

def copy_modality_files(source_base, dest_split_dir, frame_suffix, prefix_name):
    """Helper to copy all files associated with a specific frame."""
    global copied_files, missing_files
    
    # Define the exact file patterns Isaac Sim uses
    files_to_grab = {
        "rgb": [f"rgb_{frame_suffix}.png"],
        "bounding_box_2d_tight": [
            f"bounding_box_2d_tight_{frame_suffix}.npy", 
            f"bounding_box_2d_tight_labels_{frame_suffix}.json"
        ],
        "instance_segmentation": [
            f"instance_segmentation_{frame_suffix}.png", 
            f"instance_segmentation_mapping_{frame_suffix}.json"
        ],
        "semantic_segmentation": [
            f"semantic_segmentation_{frame_suffix}.png", 
            f"semantic_segmentation_labels_{frame_suffix}.json"
        ],
        "distance_to_camera": [f"distance_to_camera_{frame_suffix}.npy"]
    }
    
    for mod, filenames in files_to_grab.items():
        # Handle the difference between subfoldered static data vs flat drone data
        if os.path.isdir(os.path.join(source_base, mod)):
            mod_source_dir = os.path.join(source_base, mod)
        else:
            mod_source_dir = source_base # Flat structure (Drone)

        for filename in filenames:
            src_path = os.path.join(mod_source_dir, filename)
            
            # We rename the file slightly in the destination so we know if it was static or drone
            dest_filename = filename.replace(frame_suffix, f"{prefix_name}_{frame_suffix}")
            dest_path = os.path.join(dest_split_dir, mod, dest_filename)
            
            if os.path.exists(src_path):
                shutil.copy(src_path, dest_path)
                copied_files += 1
            else:
                missing_files += 1

# 2. Iterate through the curated YOLO images and hunt down the raw files
for split in ['train', 'val']:
    yolo_img_dir = os.path.join(YOLO_MASTER_DIR, 'images', split)
    dest_split_dir = os.path.join(OUTPUT_DIR, split)
    
    if not os.path.exists(yolo_img_dir): 
        continue
        
    yolo_images = [f for f in os.listdir(yolo_img_dir) if f.endswith('.png')]
    
    for img_name in tqdm(yolo_images, desc=f"Extracting {split} data"):
        # Example 1: drone_frame_0150.png
        # Example 2: Replicator_05_frame_0125.png
        
        if img_name.startswith("drone_frame_"):
            frame_suffix = img_name.replace("drone_frame_", "").replace(".png", "")
            copy_modality_files(DRONE_RAW_DIR, dest_split_dir, frame_suffix, prefix_name="drone")
            
        elif "_frame_" in img_name:
            parts = img_name.replace(".png", "").split("_frame_")
            replicator_folder = parts[0] # e.g., Replicator_05
            frame_suffix = parts[1]      # e.g., 0125
            
            static_source = os.path.join(STATIC_RAW_DIR, replicator_folder)
            copy_modality_files(static_source, dest_split_dir, frame_suffix, prefix_name=replicator_folder)

print("\n" + "="*60)
print("✅ MULTI-MODAL EXTRACTION COMPLETE ✅")
print(f"-> Successfully copied {copied_files} raw data files.")
if missing_files > 0:
    print(f"-> ⚠️ Note: {missing_files} files were missing in the raw dumps.")
print(f"-> Dataset ready at: {OUTPUT_DIR}")
print("="*60)