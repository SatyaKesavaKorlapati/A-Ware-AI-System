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
BLACKLIST_FILE = os.path.join(YOLO_DIR, "blacklist.txt")

RESOLUTION = (1920, 1080)
W, H = RESOLUTION
TARGET_TOTAL = 1760
VAL_SPLIT = 0.2  

omitted_classes = [
    'unknown', 'unlabelled', 'background', 
    'floor', 'ceiling', 'wall', 'rack', 'metal_rack', 'warehouse_rack'
]

class_mapping = {} 
next_class_id = 0

print("\n" + "="*60)
print("🛠️  ROCKYNOTES DATASET REPAIR & RESAMPLE UTILITY  🛠️")
print("="*60)

# 1. LOAD BLACKLIST
blacklist = set()
if os.path.exists(BLACKLIST_FILE):
    with open(BLACKLIST_FILE, 'r') as f:
        blacklist = set(line.strip() for line in f.readlines())

# 2. CLEANUP & ALIGN YOLO FOLDERS (Detect Manual Deletions)
existing_frames = set()
deleted_count = 0
train_count = 0
val_count = 0

for split in ['train', 'val']:
    img_dir = os.path.join(YOLO_DIR, 'images', split)
    lbl_dir = os.path.join(YOLO_DIR, 'labels', split)
    
    if not os.path.exists(img_dir): continue
    
    # Get all current images and labels
    imgs = set(f.replace('.png', '') for f in os.listdir(img_dir) if f.endswith('.png'))
    lbls = set(f.replace('.txt', '') for f in os.listdir(lbl_dir) if f.endswith('.txt'))
    
    # A. If a label exists but image is missing -> User deleted the image
    orphaned_labels = lbls - imgs
    for label_base in orphaned_labels:
        os.remove(os.path.join(lbl_dir, f"{label_base}.txt"))
        frame_suffix = label_base.replace("drone_frame_", "")
        blacklist.add(frame_suffix)  # Blacklist it forever
        deleted_count += 1
        
    # B. If an image exists but label is missing -> User deleted label? Fix it.
    orphaned_images = imgs - lbls
    for img_base in orphaned_images:
        os.remove(os.path.join(img_dir, f"{img_base}.png"))
        frame_suffix = img_base.replace("drone_frame_", "")
        blacklist.add(frame_suffix)
        deleted_count += 1
        
    # Re-calculate valid, perfectly matched pairs
    valid_bases = imgs.intersection(lbls)
    for base in valid_bases:
        frame_suffix = base.replace("drone_frame_", "")
        existing_frames.add(frame_suffix)
        
    if split == 'train': train_count = len(valid_bases)
    if split == 'val': val_count = len(valid_bases)

# Save updated blacklist
with open(BLACKLIST_FILE, 'w') as f:
    for item in sorted(list(blacklist)):
        f.write(f"{item}\n")

current_total = train_count + val_count
deficit = TARGET_TOTAL - current_total

print(f"-> Detected {deleted_count} manual deletions. Added to permanent blacklist.")
print(f"-> Current valid YOLO pairs : {current_total}")
print(f"-> Target total             : {TARGET_TOTAL}")
print(f"-> Deficit to fill          : {deficit} images")

if deficit <= 0:
    print("\n✅ Dataset is completely full and perfectly aligned! No resampling needed.")
    exit()

# 3. CALCULATE HOW MANY TO PUT IN TRAIN VS VAL
target_train = int(TARGET_TOTAL * (1 - VAL_SPLIT))
target_val = TARGET_TOTAL - target_train

train_deficit = max(0, target_train - train_count)
val_deficit = max(0, target_val - val_count)

# 4. SCAN RAW FOLDER FOR NEW CANDIDATES
print("\nScanning raw Isaac Sim dump for new candidate frames...")
all_available_frames = []

for file_name in os.listdir(SOURCE_DIR):
    if not (file_name.startswith("rgb_") and file_name.endswith(".png")): continue
    frame_suffix = file_name.replace("rgb_", "").replace(".png", "")
    
    # SKIP if it's already in the YOLO folder, or if the user previously deleted it!
    if frame_suffix in existing_frames or frame_suffix in blacklist:
        continue
        
    img_path = os.path.join(SOURCE_DIR, file_name)
    bbox_npy = os.path.join(SOURCE_DIR, f"bounding_box_2d_tight_{frame_suffix}.npy")
    bbox_json = os.path.join(SOURCE_DIR, f"bounding_box_2d_tight_labels_{frame_suffix}.json")
    
    if os.path.exists(bbox_npy) and os.path.exists(bbox_json):
        all_available_frames.append((img_path, bbox_npy, bbox_json, frame_suffix))

random.seed(42)
random.shuffle(all_available_frames)

# 5. FILTER AND SAMPLE NEW FRAMES
sampled_frames = []
print(f"Extracting {deficit} new high-quality frames (checking for black/empty)...")

for frame_data in all_available_frames:
    img_path, bbox_npy, bbox_json, frame_suffix = frame_data
    
    # Check 1: Pure black frame?
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None or np.max(img) == 0: continue
        
    # Check 2: Valid objects?
    bboxes = np.load(bbox_npy, allow_pickle=True)
    with open(bbox_json, 'r') as f: bb_labels = json.load(f)
        
    has_valid_class = False
    if bboxes.ndim > 0 or (bboxes.ndim == 0 and bboxes.item() is not None):
        bboxes_iterable = np.atleast_1d(bboxes)
        if bboxes_iterable[0] is not None:
            for box in bboxes_iterable:
                class_name = bb_labels.get(str(box['semanticId']), {}).get('class', 'unknown').lower()
                if class_name not in omitted_classes:
                    has_valid_class = True
                    break 
                    
    if not has_valid_class: continue

    # Passed!
    sampled_frames.append(frame_data)
    if len(sampled_frames) == deficit:
        break

if len(sampled_frames) < deficit:
    print(f"\n⚠️ WARNING: Ran out of raw frames! Only found {len(sampled_frames)} new frames.")

# 6. DISTRIBUTE AND WRITE NEW FRAMES
def get_class_id(class_name):
    global next_class_id
    if class_name not in class_mapping:
        class_mapping[class_name] = next_class_id
        next_class_id += 1
    return class_mapping[class_name]

def write_to_yolo(frame_data, split_name):
    img_path, bbox_npy, bbox_json, frame_suffix = frame_data
    new_base_name = f"drone_frame_{frame_suffix}"
    
    # Image
    shutil.copy(img_path, os.path.join(YOLO_DIR, 'images', split_name, f"{new_base_name}.png"))
    
    # Label
    bboxes = np.load(bbox_npy, allow_pickle=True)
    with open(bbox_json, 'r') as f: bb_labels = json.load(f)
        
    with open(os.path.join(YOLO_DIR, 'labels', split_name, f"{new_base_name}.txt"), 'w') as out_f:
        bboxes_iterable = np.atleast_1d(bboxes)
        for box in bboxes_iterable:
            class_name = bb_labels.get(str(box['semanticId']), {}).get('class', 'unknown').lower()
            if class_name in omitted_classes: continue
            
            c_id = get_class_id(class_name)
            x_min, y_min, x_max, y_max = box['x_min'], box['y_min'], box['x_max'], box['y_max']
            bw, bh = float(x_max - x_min), float(y_max - y_min)
            xc, yc = float(x_min + (bw / 2.0)), float(y_min + (bh / 2.0))
            out_f.write(f"{c_id} {xc/W:.6f} {yc/H:.6f} {bw/W:.6f} {bh/H:.6f}\n")

print(f"\nWriting {train_deficit} new images to TRAIN and {val_deficit} to VAL...")
for i, frame in enumerate(tqdm(sampled_frames, desc="Generating")):
    if i < train_deficit:
        write_to_yolo(frame, 'train')
    else:
        write_to_yolo(frame, 'val')

# 7. UPDATE YAML MANIFEST
yaml_path = os.path.join(YOLO_DIR, 'rockynotes.yaml')
with open(yaml_path, 'w') as f:
    f.write(f"path: .\n") 
    f.write("train: images/train\n")
    f.write("val: images/val\n\n")
    f.write("names:\n")
    inv_map = {v: k for k, v in class_mapping.items()}
    for i in range(len(inv_map)): 
        f.write(f"  {i}: {inv_map[i]}\n")

print("\n" + "="*60)
print("✅ REPAIR COMPLETE ✅")
print(f"Dataset perfectly aligned at exactly {current_total + len(sampled_frames)} images.")
print("You can now safely manually check the folders again!")
print("="*60)