# 1. FORCE PYTORCH LOAD 
import torch 

# 2. LAUNCH ISAAC SIM WITH UI ENABLED
from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": False})

import os
import time
import omni.replicator.core as rep
from omni.isaac.core import World
from omni.isaac.core.utils.stage import add_reference_to_stage

# --- CONFIGURATION ---
LOCAL_WAREHOUSE_PATH = r"D:\RAJU\rs\IssacSim\Collected_Warehouse\Warehouse.usd" 
OUTPUT_DIR = r"D:\RAJU\rs\IssacSim\rockynotes_drone_raw"
RESOLUTION = (1920, 1080)
CAPTURE_FPS = 3.0  # Exactly 3 images per second
CAPTURE_INTERVAL = 1.0 / CAPTURE_FPS

os.makedirs(OUTPUT_DIR, exist_ok=True)
world = World()

# 1. Load ONLY the Warehouse (Zero extra cameras = Zero lag)
print(f"Loading Pristine Warehouse: {LOCAL_WAREHOUSE_PATH}")
add_reference_to_stage(usd_path=LOCAL_WAREHOUSE_PATH, prim_path="/World/Warehouse")

# 2. Create the Single Drone Camera
drone_cam = rep.create.camera(position=(0, 0, 2), name="DroneCamera")
rp = rep.create.render_product(drone_cam, RESOLUTION)

# 3. Configure the Replicator Writer
writer = rep.WriterRegistry.get("BasicWriter")
writer.initialize(
    output_dir=OUTPUT_DIR,
    rgb=True,
    bounding_box_2d_tight=True,
    instance_segmentation=True
)
writer.attach([rp])

world.reset()

print("\n" + "="*60)
print("🚁 DRONE FLIGHT MODE ACTIVE 🚁")
print("1. Go to the Isaac Sim Viewport.")
print("2. Click 'Perspective' (top left) -> 'Cameras' -> Select 'Replicator/DroneCamera_X'.")
print("3. Click inside the viewport, HOLD Right-Click, and use W,A,S,D,Q,E to fly!")
print("="*60 + "\n")

frame_count = 0
last_time = time.time()

# 4. The Lightweight Flight Loop
while simulation_app.is_running():
    # Step the physics and rendering to keep your flight controls smooth
    world.step(render=True)
    
    current_time = time.time()
    
    # Trigger a background capture exactly 3 times per second
    if (current_time - last_time) >= CAPTURE_INTERVAL:
        rep.orchestrator.step()  # Snap the photo!
        frame_count += 1
        print(f"📸 [Drone Flight] Captured HD Frame {frame_count} -> Saved to disk")
        last_time = current_time

simulation_app.close()