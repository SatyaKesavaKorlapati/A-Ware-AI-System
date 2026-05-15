import os
import shutil
from tqdm import tqdm

# --- CONFIGURATION ---
STATIC_DIR = r"D:\RAJU\rs\IssacSim\rockynotes_yolo_880_filtered\1.standard_bb"
DRONE_DIR = r"D:\RAJU\rs\IssacSim\rockynotes_drone_yolo_1760"
MASTER_DIR = r"D:\RAJU\rs\IssacSim\rockynotes_master_yolo_2640"

# The master dictionary you verified
target_names = {
    0: 'pillar', 1: 'bracket', 2: 'lamp', 3: 'paper_shortcut', 4: 'sign',
    5: 'wire', 6: 'box', 7: 'floor_decal', 8: 'paper_note', 9: 'pallet',
    10: 'crate', 11: 'barel', 12: 'fuse_box', 13: 'fire_extinguisher',
    14: 'forklift', 15: 'bucket', 16: 'barcode', 17: 'bottle', 18: 'cart',
    19: 'cone', 20: 'emergency_board'
}

# 1. Clean & Create Master Folder Structure
if os.path.exists(MASTER_DIR):
    shutil.rmtree(MASTER_DIR)

for split in ['train', 'val']:
    os.makedirs(os.path.join(MASTER_DIR, 'images', split), exist_ok=True)
    os.makedirs(os.path.join(MASTER_DIR, 'labels', split), exist_ok=True)

# 2. Copy Function
def merge_into_master(source_dir, dataset_name):
    if not os.path.exists(source_dir):
        print(f"⚠️ Cannot find {source_dir}")
        return

    for split in ['train', 'val']:
        src_img_dir = os.path.join(source_dir, 'images', split)
        src_lbl_dir = os.path.join(source_dir, 'labels', split)
        
        if not os.path.exists(src_img_dir): continue
        
        images = [f for f in os.listdir(src_img_dir) if f.endswith('.png')]
        
        for img_name in tqdm(images, desc=f"Copying {dataset_name} ({split})"):
            lbl_name = img_name.replace('.png', '.txt')
            
            src_img_path = os.path.join(src_img_dir, img_name)
            src_lbl_path = os.path.join(src_lbl_dir, lbl_name)
            
            dest_img_path = os.path.join(MASTER_DIR, 'images', split, img_name)
            dest_lbl_path = os.path.join(MASTER_DIR, 'labels', split, lbl_name)
            
            # Only copy if both image and label exist
            if os.path.exists(src_img_path) and os.path.exists(src_lbl_path):
                shutil.copy(src_img_path, dest_img_path)
                shutil.copy(src_lbl_path, dest_lbl_path)

print("\n" + "="*50)
print("🚀 INITIATING FINAL MERGE 🚀")
print("="*50)

# Execute the merge
merge_into_master(STATIC_DIR, "Static Dataset (880)")
merge_into_master(DRONE_DIR, "Drone Dataset (1760)")

# 3. Write the exact data.yaml manifest
yaml_path = os.path.join(MASTER_DIR, 'data.yaml')
with open(yaml_path, 'w') as f:
    f.write("path: .\n") 
    f.write("train: images/train\n")
    f.write("val: images/val\n\n")
    f.write("names:\n")
    for c_id, name in target_names.items():
        f.write(f"  {c_id}: {name}\n")

print("\n" + "="*50)
print("✅ MASTER DATASET ASSEMBLED ✅")
print(f"Location: {MASTER_DIR}")
print("Contains ONLY: /images, /labels, and data.yaml")
print("="*50)