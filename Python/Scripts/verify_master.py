import os
import cv2
import random

# --- CONFIGURATION ---
MASTER_DIR = r"D:\RAJU\rs\IssacSim\rockynotes_master_yolo_2640"
SAMPLES_TO_DRAW = 30  # Number of random images to verify

print("\n" + "="*50)
print("🔍 FINAL MASTER DATASET VERIFICATION 🔍")
print("Controls:")
print(" - Press SPACEBAR (or any key) for the next image.")
print(" - Press ESC to close and exit.")
print("="*50)

# 1. Parse the Strict Master YAML
yaml_path = os.path.join(MASTER_DIR, "data.yaml")
class_names = {}

if not os.path.exists(yaml_path):
    print(f"❌ Error: data.yaml not found at {yaml_path}")
    exit()

with open(yaml_path, 'r') as f:
    in_names = False
    for line in f:
        if line.strip().startswith('names:'):
            in_names = True
            continue
        if in_names and ':' in line:
            try:
                parts = line.split(':')
                c_id = int(parts[0].strip())
                c_name = parts[1].strip().replace("'", "").replace('"', "")
                class_names[c_id] = c_name
            except:
                pass

print(f"Loaded {len(class_names)} strict classes from data.yaml.")

# 2. Assign distinct colors for each class
random.seed(42)
class_colors = {c_id: (random.randint(50, 255), random.randint(100, 255), random.randint(50, 255)) for c_id in class_names}

# 3. Gather all images from Train and Val
all_images = []
for split in ['train', 'val']:
    img_dir = os.path.join(MASTER_DIR, 'images', split)
    if os.path.exists(img_dir):
        for img_name in os.listdir(img_dir):
            if img_name.endswith('.png'):
                all_images.append((split, img_name))

if not all_images:
    print("❌ Error: No images found in the master directory.")
    exit()

# Pick random samples
sampled_images = random.sample(all_images, min(SAMPLES_TO_DRAW, len(all_images)))

# Set up an adjustable window
cv2.namedWindow("Master Verification", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Master Verification", 1280, 720) 

# 4. Display the bounding boxes
for split, img_name in sampled_images:
    img_path = os.path.join(MASTER_DIR, 'images', split, img_name)
    lbl_path = os.path.join(MASTER_DIR, 'labels', split, img_name.replace('.png', '.txt'))
    
    img = cv2.imread(img_path)
    if img is None:
        continue
        
    h, w, _ = img.shape
    
    if os.path.exists(lbl_path):
        with open(lbl_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 5:
                    c_id = int(parts[0])
                    x_center, y_center, bw, bh = map(float, parts[1:])
                    
                    # Convert YOLO normalized math to absolute pixels
                    x_min = int((x_center - bw / 2) * w)
                    y_min = int((y_center - bh / 2) * h)
                    x_max = int((x_center + bw / 2) * w)
                    y_max = int((y_center + bh / 2) * h)
                    
                    c_name = class_names.get(c_id, f"Unknown_{c_id}")
                    color = class_colors.get(c_id, (0, 0, 255))
                    
                    # Draw Box
                    cv2.rectangle(img, (x_min, y_min), (x_max, y_max), color, 2)
                    
                    # Draw Label Background
                    (text_w, text_h), _ = cv2.getTextSize(c_name, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                    cv2.rectangle(img, (x_min, y_min - text_h - 5), (x_min + text_w, y_min), color, -1)
                    
                    # Draw Text
                    cv2.putText(img, c_name, (x_min, y_min - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    else:
        cv2.putText(img, "NO LABEL FILE FOUND", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

    # Show the image
    cv2.imshow("Master Verification", img)
    
    # Wait for key press
    key = cv2.waitKey(0) & 0xFF
    if key == 27: # ASCII code for ESC
        print("\nVerification stopped early by user.")
        break

cv2.destroyAllWindows()
print("\n✅ Verification complete!")