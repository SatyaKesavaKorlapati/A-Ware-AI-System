# 1. FORCE PYTORCH LOAD
import torch 

# 2. LAUNCH ISAAC SIM WITH THE UI OPEN
from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": False})

import json
from pxr import UsdGeom, Gf
from omni.isaac.core import World
from omni.isaac.core.utils.stage import add_reference_to_stage
import omni.usd

# --- CONFIGURATION ---
LOCAL_WAREHOUSE_PATH = "D:/RAJU/rs/IssacSim/Collected_Warehouse/Warehouse.usd" 
JSON_PATH = "D:\\RAJU\\rs\\IssacSim\\Cam_configs\\all_22_cameras.json"

world = World()

print(f"Loading Pristine Warehouse: {LOCAL_WAREHOUSE_PATH}")
add_reference_to_stage(usd_path=LOCAL_WAREHOUSE_PATH, prim_path="/World/Warehouse")

print(f"Injecting cameras from: {JSON_PATH}")
with open(JSON_PATH, 'r') as f:
    camera_data = json.load(f)

stage = omni.usd.get_context().get_stage()

# Dynamically build the cameras from your JSON
for cam_key, cam_info in camera_data.items():
    prim_path = "/World" + cam_info["prim_path"]
    cam = UsdGeom.Camera.Define(stage, prim_path)
    
    # 1. Set Exact Position (Double precision is correct here)
    pos = cam_info["position"]
    cam.AddTranslateOp().Set(Gf.Vec3d(pos["x"], pos["y"], pos["z"]))
    
    # 2. Set Exact Orientation (FIXED: Using Gf.Quatf for single-precision)
    quat = cam_info["orientation_quat"]
    q = Gf.Quatf(quat["w"], quat["x"], quat["y"], quat["z"]) 
    cam.AddOrientOp().Set(q)
    
    # 3. Set Lens Properties
    cam.GetFocalLengthAttr().Set(cam_info["focal_length_mm"])
    cam.GetHorizontalApertureAttr().Set(cam_info["horizontal_aperture"])
    cam.GetVerticalApertureAttr().Set(cam_info["vertical_aperture"])
    
    print(f"Successfully spawned: {prim_path}")

world.reset()

print("\n" + "="*50)
print("🎥 LIVE ENVIRONMENT ACTIVE 🎥")
print("1. Go to the Isaac Sim window.")
print("2. Look at the 'Stage' panel -> expand /World to see your 9 injected cameras.")
print("3. Click 'Perspective' -> 'Cameras' and select one to look through its lens.")
print("4. Check if the warehouse is fully textured and the framing is right.")
print("="*50 + "\n")

# Keep the window open for your inspection
while simulation_app.is_running():
    world.step(render=True)

simulation_app.close()