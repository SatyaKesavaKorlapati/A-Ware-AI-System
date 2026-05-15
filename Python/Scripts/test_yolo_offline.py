import os
import cv2
from ultralytics import YOLO

# --- CONFIGURATION ---
MODEL_PATH = r"D:\RAJU\rs\IssacSim\Python\Models\lar1r.pt"

# Pointing this to the validation set we built earlier
TEST_IMAGES_DIR = r"D:\RAJU\rs\IssacSim\rockynotes_master_yolo_2640\images\val"

print("\n" + "="*50)
print("🧠 OFFLINE YOLO INFERENCE (TESTING SET) 🧠")
print("Controls:")
print(" - Press SPACEBAR (or any key) for the next image.")
print(" - Press ESC to close and exit.")
print("="*50)

# 1. Load the Model
print(f"\nLoading model from {MODEL_PATH}...")
try:
    model = YOLO(MODEL_PATH)
    print("✅ Model loaded successfully!")
except Exception as e:
    print(f"❌ Failed to load model: {e}")
    exit()

# 2. Get all images from the validation folder
if not os.path.exists(TEST_IMAGES_DIR):
    print(f"❌ Error: Cannot find folder {TEST_IMAGES_DIR}")
    exit()

image_files = [f for f in os.listdir(TEST_IMAGES_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

if not image_files:
    print(f"❌ No images found in {TEST_IMAGES_DIR}")
    exit()

print(f"Found {len(image_files)} images to test. Starting viewer...\n")

# Set up a scalable window
cv2.namedWindow("YOLO Inference", cv2.WINDOW_NORMAL)
cv2.resizeWindow("YOLO Inference", 1280, 720)

# 3. Loop and Infer
for img_name in image_files:
    img_path = os.path.join(TEST_IMAGES_DIR, img_name)
    
    # Run inference (conf=0.25 to catch most objects)
    results = model(img_path, conf=0.25, verbose=False)
    
    # Plot the results (this automatically draws the boxes, colors, and labels)
    annotated_img = results[0].plot()
    
    # Display the image
    cv2.imshow("YOLO Inference", annotated_img)
    
    # Wait for user input
    key = cv2.waitKey(0) & 0xFF
    if key == 27:  # ESC key
        print("\nTesting stopped early by user.")
        break

cv2.destroyAllWindows()
print("\n✅ Testing complete!")