# Launch Isaac Sim with the UI enabled for free-cam control
from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": False})

import cv2
import time
import numpy as np
import omni.replicator.core as rep
from ultralytics import YOLO

# --- CONFIGURATION ---
MODEL_PATH = r"D:\RAJU\rs\IssacSim\Python\Models\lar1r.pt" 

print("\nLoading YOLO Model into VRAM...")
model = YOLO(MODEL_PATH)
print("Model loaded successfully!")

# Hook into the default Perspective camera that you use to fly around
print("Hooking into Isaac Sim active viewport...")
render_product = rep.create.render_product("/OmniverseKit_Persp", (1280, 720))

# Create an RGB annotator to grab the frames
rgb_annotator = rep.AnnotatorRegistry.get_annotator("rgb")
rgb_annotator.attach([render_product])

cv2.namedWindow("YOLO Live Feed", cv2.WINDOW_NORMAL)
cv2.resizeWindow("YOLO Live Feed", 1280, 720)

print("\n" + "="*50)
print("🚀 LIVE INFERENCE ACTIVE 🚀")
print("1. Load your warehouse USD in the Isaac Sim window.")
print("2. Click the Isaac Sim window and use W, A, S, D + Right Click to fly.")
print("3. Watch the OpenCV window for real-time bounding boxes!")
print("4. Press ESC on the OpenCV window to exit.")
print("="*50)

# For FPS calculation
prev_time = 0

# The Live Application Loop
while simulation_app.is_running():
    # Step the simulation forward
    simulation_app.update()
    
    # Grab the current frame from the camera
    rgb_data = rgb_annotator.get_data()
    
    if rgb_data is not None and rgb_data.size > 0:
        # Calculate FPS
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time) if prev_time > 0 else 0
        prev_time = curr_time
        
        # Isaac Sim outputs RGBA, OpenCV and YOLO need BGR
        img_bgr = cv2.cvtColor(rgb_data, cv2.COLOR_RGBA2BGR)
        
        # Run YOLO Inference (verbose=False stops terminal spam)
        results = model(img_bgr, conf=0.25, verbose=False)
        
        # Let Ultralytics draw the bounding boxes and labels automatically
        annotated_frame = results[0].plot()
        
        # Draw FPS on the top left corner
        cv2.putText(annotated_frame, f"FPS: {int(fps)}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # Display the live feed
        cv2.imshow("YOLO Live Feed", annotated_frame)
        
        if cv2.waitKey(1) & 0xFF == 27: # ESC key
            print("Shutting down...")
            break

cv2.destroyAllWindows()
simulation_app.close()