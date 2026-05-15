import os
import json
import numpy as np
import shutil
import random
import cv2

# --- CONFIGURATION ---
SOURCE_DIR = r"D:\RAJU\rs\IssacSim\rockynotes_dataset_final"
YOLO_DIR = r"D:\RAJU\rs\IssacSim\rockynotes_yolo_880_filtered" # New folder name to avoid confusion

BB_DIR = os.path.join(YOLO_DIR, "1.standard_bb")
SEG_DIR = os.path.join(YOLO_DIR, "2.instance_segmentation")

RESOLUTION = (1920, 1080)
W, H = RESOLUTION
VAL_SPLIT = 0.2  
FRAMES_PER_CAMERA = 40  # 22 cameras * 40 = 880 total

# 🚨 THE BLACKLIST: Add any massive structural classes here 🚨
omitted_classes = [
    'unknown', 'unlabelled', 'background', 
    'floor', 'ceiling', 'wall', 'rack', 'metal_rack', 'warehouse_rack'
]

# 1. Clean & Create Dual YOLO Folder Structure
if os.path.exists(YOLO_DIR):
    shutil.rmtree(YOLO_DIR)

for base_dir in [BB_DIR, SEG_DIR]:
    for split in ['train', 'val']:
        os.makedirs(os.path.join(base_dir, 'images', split), exist_ok=True)
        os.makedirs(os.path.join(base_dir, 'labels', split), exist_ok=True)

class_mapping = {} 
next_class_id = 0
all_data = [] 

print(f"Scanning rockynotes dataset to sample {FRAMES_PER_CAMERA} frames per camera...")

# 2. Collect Valid Frames
folders = [f for f in os.listdir(SOURCE_DIR) if f.startswith("Replicator")]

for folder in folders:
    rgb_dir = os.path.join(SOURCE_DIR, folder, "rgb")
    bbox_dir = os.path.join(SOURCE_DIR, folder, "bounding_box_2d_tight")
    inst_dir = os.path.join(SOURCE_DIR, folder, "instance_segmentation")
    
    if not (os.path.exists(rgb_dir) and os.path.exists(bbox_dir) and os.path.exists(inst_dir)): 
        continue
    
    valid_frames = []
    
    for img_file in os.listdir(rgb_dir):
        if not img_file.endswith(".png"): continue
        
        frame_suffix = img_file.replace("rgb_", "").replace(".png", "")
        img_path = os.path.join(rgb_dir, img_file)
        
        # Locate matching data files
        bbox_npy = os.path.join(bbox_dir, f"bounding_box_2d_tight_{frame_suffix}.npy")
        bbox_json = os.path.join(bbox_dir, f"bounding_box_2d_tight_labels_{frame_suffix}.json")
        inst_img = os.path.join(inst_dir, f"instance_segmentation_{frame_suffix}.png")
        inst_json = os.path.join(inst_dir, f"instance_segmentation_mapping_{frame_suffix}.json")
        
        # Check if all files actually generated for this frame
        if os.path.exists(bbox_npy) and os.path.exists(bbox_json) and os.path.exists(inst_img) and os.path.exists(inst_json):
            valid_frames.append((img_path, bbox_npy, bbox_json, inst_img, inst_json, folder, frame_suffix))
            
    if len(valid_frames) > FRAMES_PER_CAMERA:
        sampled_frames = random.sample(valid_frames, FRAMES_PER_CAMERA)
    else:
        sampled_frames = valid_frames
        
    all_data.extend(sampled_frames)
    print(f"  [{folder}] Sampled {len(sampled_frames)} frames.")

# 3. Shuffle global dataset for Train/Val split
random.seed(42)
random.shuffle(all_data)

split_idx = int(len(all_data) * (1 - VAL_SPLIT))
train_data = all_data[:split_idx]
val_data = all_data[split_idx:]

def get_class_id(class_name):
    global next_class_id
    if class_name not in class_mapping:
        class_mapping[class_name] = next_class_id
        next_class_id += 1
    return class_mapping[class_name]

def process_split(data_list, split_name):
    for img_path, bbox_npy, bbox_json, inst_img, inst_json, folder, frame_suffix in data_list:
        
        new_base_name = f"{folder}_frame_{frame_suffix}"
        
        # --- COPY IMAGES TO BOTH FOLDERS ---
        bb_img_dest = os.path.join(BB_DIR, 'images', split_name, f"{new_base_name}.png")
        seg_img_dest = os.path.join(SEG_DIR, 'images', split_name, f"{new_base_name}.png")
        shutil.copy(img_path, bb_img_dest)
        shutil.copy(img_path, seg_img_dest)
        
        # --- 1. GENERATE YOLO BOUNDING BOXES (.txt) ---
        dest_bb_label = os.path.join(BB_DIR, 'labels', split_name, f"{new_base_name}.txt")
        bboxes = np.load(bbox_npy)
        with open(bbox_json, 'r') as f: bb_labels = json.load(f)
            
        with open(dest_bb_label, 'w') as out_f:
            for box in bboxes:
                # Convert to lowercase to make filtering robust
                class_name = bb_labels.get(str(box['semanticId']), {}).get('class', 'unknown').lower()
                
                # Apply our new structural blacklist
                if class_name in omitted_classes: 
                    continue
                
                c_id = get_class_id(class_name)
                x_min, y_min, x_max, y_max = box['x_min'], box['y_min'], box['x_max'], box['y_max']
                
                bw, bh = float(x_max - x_min), float(y_max - y_min)
                xc, yc = float(x_min + (bw / 2.0)), float(y_min + (bh / 2.0))
                
                out_f.write(f"{c_id} {xc/W:.6f} {yc/H:.6f} {bw/W:.6f} {bh/H:.6f}\n")

        # --- 2. GENERATE YOLO INSTANCE SEGMENTATION POLYGONS (.txt) ---
        dest_seg_label = os.path.join(SEG_DIR, 'labels', split_name, f"{new_base_name}.txt")
        
        # Load mask and class mapping
        mask = cv2.imread(inst_img, cv2.IMREAD_UNCHANGED)
        with open(inst_json, 'r') as f: inst_labels = json.load(f)
        
        with open(dest_seg_label, 'w') as out_f:
            unique_ids = np.unique(mask)
            for uid in unique_ids:
                if uid == 0: continue # Skip background
                
                # Fetch class name mapped to this specific instance pixel value
                class_name = inst_labels.get(str(uid), {}).get('class', 'unknown').lower()
                
                # Apply our new structural blacklist here too!
                if class_name in omitted_classes: 
                    continue
                
                c_id = get_class_id(class_name)
                
                # Isolate this specific object and trace its contours
                binary_mask = (mask == uid).astype(np.uint8) * 255
                contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                for contour in contours:
                    # YOLO requires polygons to have at least 3 points
                    if len(contour) >= 3:
                        contour = contour.flatten()
                        polygon_str = f"{c_id}"
                        for i in range(0, len(contour), 2):
                            px, py = contour[i] / W, contour[i+1] / H
                            polygon_str += f" {px:.6f} {py:.6f}"
                        out_f.write(polygon_str + "\n")

print(f"\nProcessing {len(train_data)} Training Images for both datasets...")
process_split(train_data, 'train')

print(f"Processing {len(val_data)} Validation Images for both datasets...")
process_split(val_data, 'val')

# 4. Generate the YAML manifests
for d in [BB_DIR, SEG_DIR]:
    yaml_path = os.path.join(d, 'rockynotes.yaml')
    with open(yaml_path, 'w') as f:
        f.write(f"path: .\n") 
        f.write("train: images/train\n")
        f.write("val: images/val\n\n")
        f.write("names:\n")
        inv_map = {v: k for k, v in class_mapping.items()}
        for i in range(len(inv_map)): f.write(f"  {i}: {inv_map[i]}\n")

print("\n" + "="*70)
print(f"✅ DUAL DATASET GENERATION COMPLETE (FILTERED) ! ✅")
print(f"-> Object Detection ready at: {BB_DIR}")
print(f"-> Instance Segmentation ready at: {SEG_DIR}")
print(f"Detected Classes (Giant boxes successfully removed): {list(class_mapping.keys())}")
print("="*70)