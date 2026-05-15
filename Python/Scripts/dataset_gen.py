# 1. FORCE PYTORCH LOAD 
import torch 

# 2. LAUNCH ISAAC SIM HEADLESS
from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})

import os
import json
import gc
import shutil
import time
from pxr import UsdGeom, Gf
from omni.isaac.core import World
from omni.isaac.core.utils.stage import add_reference_to_stage
import omni.usd
import omni.replicator.core as rep
from tqdm import tqdm

def organize_output_into_folders(output_dir):
    """Automatically rebuilds the Replicator subfolder structure."""
    categories = [
        "rgb", 
        "distance_to_camera", 
        "bounding_box_2d_tight", 
        "semantic_segmentation", 
        "instance_segmentation"
    ]
    for cat in categories:
        os.makedirs(os.path.join(output_dir, cat), exist_ok=True)
        
    for filename in os.listdir(output_dir):
        file_path = os.path.join(output_dir, filename)
        if os.path.isdir(file_path):
            continue
        for cat in categories:
            if filename.startswith(cat):
                shutil.move(file_path, os.path.join(output_dir, cat, filename))
                break

# --- CONFIGURATION ---
FRAMES_PER_CAMERA = 200
SUB_BATCH_SIZE = 50       
RESOLUTION = (1920, 1080)  

OUTPUT_DIR = "D:/RAJU/rs/IssacSim/rockynotes_dataset_final"
LOCAL_WAREHOUSE_PATH = "D:/RAJU/rs/IssacSim/Collected_Warehouse/Warehouse.usd" 
JSON_PATH = "D:/RAJU/rs/IssacSim/Cam_configs/all_22_cameras.json"

os.makedirs(OUTPUT_DIR, exist_ok=True)
world = World()

print(f"Loading Warehouse...")
add_reference_to_stage(usd_path=LOCAL_WAREHOUSE_PATH, prim_path="/World/Warehouse")

print(f"Injecting cameras from JSON...")
with open(JSON_PATH, 'r') as f:
    camera_data = json.load(f)

stage = omni.usd.get_context().get_stage()
camera_paths = []

for cam_key, cam_info in camera_data.items():
    raw_path = cam_info["prim_path"]
    if not raw_path.startswith("/World"):
        prim_path = "/World" + (raw_path if raw_path.startswith("/") else "/" + raw_path)
    else:
        prim_path = raw_path

    cam = UsdGeom.Camera.Define(stage, prim_path)
    pos = cam_info["position"]
    cam.AddTranslateOp().Set(Gf.Vec3d(pos["x"], pos["y"], pos["z"]))
    quat = cam_info["orientation_quat"]
    q = Gf.Quatf(quat["w"], quat["x"], quat["y"], quat["z"]) 
    cam.AddOrientOp().Set(q)
    cam.GetFocalLengthAttr().Set(cam_info["focal_length_mm"])
    cam.GetHorizontalApertureAttr().Set(cam_info["horizontal_aperture"])
    cam.GetVerticalApertureAttr().Set(cam_info["vertical_aperture"])
    camera_paths.append(prim_path)

num_sub_batches = FRAMES_PER_CAMERA // SUB_BATCH_SIZE

# --- BULLETPROOF VRAM SUB-BATCH LOOP ---
for i, cam_path in enumerate(camera_paths):
    cam_name = cam_path.split("/")[-1]
    folder_name = cam_name.replace("Camera", "Replicator")
    cam_output_dir = os.path.join(OUTPUT_DIR, folder_name)
    os.makedirs(cam_output_dir, exist_ok=True)
    
    print(f"\n[{i+1}/{len(camera_paths)}] Processing 200 frames for: {folder_name}")
    
    # Init fresh writer per camera to prevent buffer collisions
    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(
        output_dir=cam_output_dir, 
        rgb=True, distance_to_camera=True, bounding_box_2d_tight=True,      
        semantic_segmentation=True, instance_segmentation=True       
    )
    
    rp = rep.create.render_product(cam_path, RESOLUTION)
    writer.attach([rp])
    
    # Warm up Shaders
    for _ in range(15):
        world.step(render=True)

    # SUB-BATCH EXECUTION
    for batch_idx in range(num_sub_batches):
        for frame in tqdm(range(SUB_BATCH_SIZE), desc=f"  -> Sub-batch {batch_idx + 1}/{num_sub_batches}"):
            world.step(render=True)
            rep.orchestrator.step() 
            
        # 1. Wait for IO queue to finish
        rep.orchestrator.wait_until_complete()
        
        # 2. Hard pause to let the hard drive finish writing the 50 frames
        time.sleep(1.5)
        
        # 3. Clean CUDA mapped memory
        gc.collect()
        torch.cuda.empty_cache()
    
    # --- CAMERA TEARDOWN AND DEEP VRAM FLUSH ---
    writer.detach()
    rp.destroy()
    
    # CRITICAL: Step the world a few times so the renderer processes the camera deletion
    # If we don't do this, the VRAM stays permanently mapped to the destroyed camera
    for _ in range(5):
        world.step(render=True)
        
    gc.collect()
    torch.cuda.empty_cache()
    
    # Hard pause before initializing the next camera
    time.sleep(2.0)
    
    # Organize files
    organize_output_into_folders(cam_output_dir)

print("\n" + "="*70)
print(f"✅ BULLETPROOF 4,400-IMAGE DATASET GENERATION COMPLETE! ✅")
print("="*70)
simulation_app.close()