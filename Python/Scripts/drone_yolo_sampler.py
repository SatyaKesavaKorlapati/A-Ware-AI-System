import os
import json
import numpy as np
import shutil
import random
import cv2
from tqdm import tqdm

# --- CONFIGURATION ---
SOURCE_DIR = r"D:\RAJU\rs\IssacSim\rockynotes_drone_raw"
YOLO_DIR = r"D:\RAJU\rs\IssacSim\rockynotes_drone_yolo_1760"

RESOLUTION = (1920, 1080)
W, H = RESOLUTION
VAL_SPLIT = 0.2  
TARGET_IMAGES = 1760  # 880 * 2

# 🚨 THE STRICT WHITELIST MAPPING 🚨
target_names = {
    0: 'pillar', 1: 'bracket', 2: 'lamp', 3: 'paper_shortcut', 4: 'sign',
    5: 'wire', 6: 'box', 7: 'floor_decal', 8: 'paper_note', 9: 'pallet',
    10: 'crate', 11: 'barel', 12: 'fuse_box', 13: 'fire_extinguisher',
    14: 'forklift', 15: 'bucket', 16: 'barcode', 17: 'bottle', 18: 'cart',
    19: 'cone', 20: 'emergency_board'
}

# Reverse it for fast text-to-ID lookups (all lowercase for safety)
class_to_id = {name.lower(): c_id for c_id, name in target_names.items()}

# 1. Clean & Create YOLO Folder Structure
if os.path.exists(YOLO_DIR):
    shutil.rmtree(YOLO_DIR)

for split in ['train', 'val']:
    os.makedirs(os.path.join(YOLO_DIR, 'images', split), exist_ok=True)
    os.makedirs(os.path.join(YOLO_DIR, 'labels', split), exist_ok=True)

all_available_frames = []

print(f"Scanning flat drone dataset for file paths...")

# 2. Collect All Frame Paths First (Fast)
for file_name in os.listdir(SOURCE_DIR):
    if not (file_name.startswith("rgb_") and file_name.endswith(".png")): 
        continue
    
    frame_suffix = file_name.replace("rgb_", "").replace(".png", "")
    img_path = os.path.join(SOURCE_DIR, file_name)
    
    bbox_npy = os.path.join(SOURCE_DIR, f"bounding_box_2d_tight_{frame_suffix}.npy")
    bbox_json = os.path.join(SOURCE_DIR, f"bounding_box_2d_tight_labels_{frame_suffix}.json")
    
    if os.path.exists(bbox_npy) and os.path.exists(bbox_json):
        all_available_frames.append((img_path, bbox_npy, bbox_json, frame_suffix))

print(f"Found {len(all_available_frames)} candidate frames.")

# 3. Filter Black Frames AND Empty Frames, then Sample Exactly 1,760
random.seed(42)
random.shuffle(all_available_frames) 

sampled_frames = []
black_frames_skipped = 0
empty_frames_skipped = 0

print(f"Verifying images (Discarding black frames and frames with 0 target objects)...")
for frame_data in tqdm(all_available_frames, desc="Filtering"):
    img_path, bbox_npy, bbox_json, frame_suffix = frame_data
    
    # Check 1: Is it a pure black frame?
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None or np.max(img) == 0:
        black_frames_skipped += 1
        continue
        
    # Check 2: Does it have at least ONE object from our STRICT whitelist?
    bboxes = np.load(bbox_npy, allow_pickle=True)
    with open(bbox_json, 'r') as f: 
        bb_labels = json.load(f)
        
    has_valid_class = False
    
    if bboxes.ndim > 0 or (bboxes.ndim == 0 and bboxes.item() is not None):
        bboxes_iterable = np.atleast_1d(bboxes)
        if bboxes_iterable[0] is not None:
            for box in bboxes_iterable:
                class_name = bb_labels.get(str(box['semanticId']), {}).get('class', 'unknown').lower()
                
                # Check against our strict mapping instead of a blacklist
                if class_name in class_to_id:
                    has_valid_class = True
                    break 
                    
    if not has_valid_class:
        empty_frames_skipped += 1
        continue

    # Passed all checks!
    sampled_frames.append(frame_data)
    
    # Stop exactly when we hit our target
    if len(sampled_frames) == TARGET_IMAGES:
        break

if len(sampled_frames) < TARGET_IMAGES:
    print(f"Warning: Only found {len(sampled_frames)} valid frames out of {TARGET_IMAGES} requested.")

# 4. Shuffle and Split (Train/Val)
random.shuffle(sampled_frames)
split_idx = int(len(sampled_frames) * (1 - VAL_SPLIT))
train_data = sampled_frames[:split_idx]
val_data = sampled_frames[split_idx:]

def process_split(data_list, split_name):
    for img_path, bbox_npy, bbox_json, frame_suffix in tqdm(data_list, desc=f"Writing {split_name} data"):
        
        new_base_name = f"drone_frame_{frame_suffix}"
        
        # Copy Image
        img_dest = os.path.join(YOLO_DIR, 'images', split_name, f"{new_base_name}.png")
        shutil.copy(img_path, img_dest)
        
        # Generate YOLO Bounding Boxes (.txt)
        dest_bb_label = os.path.join(YOLO_DIR, 'labels', split_name, f"{new_base_name}.txt")
        bboxes = np.load(bbox_npy, allow_pickle=True)
        
        with open(bbox_json, 'r') as f: 
            bb_labels = json.load(f)
            
        with open(dest_bb_label, 'w') as out_f:
            bboxes_iterable = np.atleast_1d(bboxes)
            if bboxes_iterable[0] is not None:
                for box in bboxes_iterable:
                    class_name = bb_labels.get(str(box['semanticId']), {}).get('class', 'unknown').lower()
                    
                    # IF it is in our strict whitelist, write it. Otherwise, ignore it.
                    if class_name in class_to_id: 
                        c_id = class_to_id[class_name]
                        x_min, y_min, x_max, y_max = box['x_min'], box['y_min'], box['x_max'], box['y_max']
                        
                        bw, bh = float(x_max - x_min), float(y_max - y_min)
                        xc, yc = float(x_min + (bw / 2.0)), float(y_min + (bh / 2.0))
                        
                        out_f.write(f"{c_id} {xc/W:.6f} {yc/H:.6f} {bw/W:.6f} {bh/H:.6f}\n")

print(f"\nProcessing {len(train_data)} Training Images and {len(val_data)} Validation Images...")
process_split(train_data, 'train')
process_split(val_data, 'val')

# 5. Generate the YAML manifest using the strict dictionary
yaml_path = os.path.join(YOLO_DIR, 'data.yaml')
with open(yaml_path, 'w') as f:
    f.write(f"path: .\n") 
    f.write("train: images/train\n")
    f.write("val: images/val\n\n")
    f.write("names:\n")
    for c_id, name in target_names.items():
        f.write(f"  {c_id}: {name}\n")

print("\n" + "="*70)
print(f"✅ STRICT PREMIUM DRONE DATASET COMPLETE! ✅")
print(f"-> Skipped {black_frames_skipped} pure black frames.")
print(f"-> Skipped {empty_frames_skipped} frames with zero target objects.")
print(f"-> Formatted exactly {len(sampled_frames)} premium images at: {YOLO_DIR}")
print("="*70)