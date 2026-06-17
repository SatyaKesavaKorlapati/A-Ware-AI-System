# Visual Language Model (VLM) Training Data Generation: Synthetic Multi-Camera RGBD Dataset and Warehouse Intelligence Application for Object Detection

**Authors:** SatyaKesava Korlapati
**Institution:** Indian Institute of Technology Mandi

## 1. Introduction & Background
Training robust perception models for warehouse robotics requires large, diverse, precisely annotated datasets. Real-world collection in active warehouses is expensive, hazardous, and practically infeasible at scale. Synthetic data generation via photo-realistic simulators addresses these challenges.

This project focuses on:
1. Generating a multi-camera RGBD dataset with synchronised spatial and temporal alignment from a photorealistic simulator.
2. Producing pixel-accurate annotations across five modalities automatically.
3. Removing annotation pollution from large structural scene classes that suppress recall on informative object categories.

## 2. Methodology: Dataset Generation
### Simulator Selection
NVIDIA Isaac Sim was chosen over AirSim and Unity Perception for its native USD support, synchronised multi-sensor capture, automatic ground-truth generation across all modalities, and seamless PyTorch integration.

### Warehouse Scene
A USD warehouse asset was loaded into the stage. The scene contains industrial metal racks, cardboard boxes, pallets, forklift trucks, fire extinguishers, crates, barrels, cones, barcodes, and autonomous mobile robot (AMR) carts. The scene layout comprises 6 aisles and 12 racks (Aisle N corresponds to Racks 2N − 1 and 2N).

### Multi-Camera RGBD Setup
- **Static Camera Rig:** 22 cameras placed at ceiling height and mid-rack elevation for wide, overlapping floor coverage. Resolution: 1920×1080.
- **Drone Camera:** A dynamic drone camera following a scripted trajectory at 3 FPS, performing low-altitude and high-altitude sweeps.

### Captured Modalities
1. **RGB:** 1920×1080 full-colour image.
2. **Bounding Box 2D Tight:** per-object AABB.
3. **Instance Segmentation:** per-instance colour mask.
4. **Semantic Segmentation:** class-level colour mask.
5. **Depth:** per-pixel metric distance to camera.

### Dataset Composition
| Source | Frames | Notes |
|---|---|---|
| 22 static cameras x 40 | 880 | Floor/rack coverage |
| Drone camera — pass 1 | 880 | Low-altitude sweep |
| Drone camera — pass 2 | 880 | High-altitude sweep |
| **Total** | **2,640** | **masterwarehouse-2640** |

## 3. Annotation Pipeline & Class Filtering
Annotations are generated automatically from Isaac Sim Replicator output.

**Class Filtering:** Initial training showed structural classes (floor, ceiling, wall, rack, metal_rack, warehouse_rack, unknown, background) dominated annotation counts and suppressed recall on informative object classes. These were explicitly blacklisted.

### Dataset Versions
| Dataset | Frames | Filter | Runs |
|---|---|---|---|
| warehouse-bb | 880 | None | runx12, runx2 |
| warehouse-bb-4 | 880 | Applied | s_12804, x_12802 |
| **masterwarehouse-2640** | **2,640** | **Applied** | **LAR1r, MED1r-2, x640** |

## 4. YOLO26 Training & Evaluation
Training was performed using the YOLO26 family with the auto optimiser, AMP enabled, 100 epochs, and standard YOLO augmentations (HSV jitter, mosaic, random erasing, RandAugment).

### Configuration Analysis (Best vs Baseline)
| Parameter | Col 1 (Optimised) | Col 2 (Baseline) |
|---|---|---|
| imgsz | 1280 | 640 |
| batch | 3 (fixed) | -1 (auto) |
| iou | 0.85 | 0.70 |
| max_det | 1500 | 300 |
| Frames | 2,640 | 880 |
| Class filter | Applied | None |
| **Best model variant** | **yolo26l** | **yolo26x / yolo26s** |

### Complete Experimental Training Log
*Best model (LAR1r) highlighted.*

| Run | Model | Dataset | imgsz | batch | IoU | max_det | Ep. | P | R | mAP50 | mAP50-95 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **LAR1r** | **yolo26l** | **masterwarehouse-2640** | **1280** | **3** | **0.85** | **1500** | **100** | **0.919** | **0.697** | **0.735** | **0.612** |
| MED1r-2 | yolo26m | masterwarehouse-2640 | 1280 | 3 | 0.85 | 1500 | 100 | 0.906 | 0.691 | 0.725 | 0.600 |
| yolo26x_640_e150 | yolo26x | masterwarehouse-2640 | 640 | -1 | 0.70 | 300 | 150 | 0.935 | 0.540 | 0.543 | 0.464 |
| runx12 | yolo26l | warehouse-bb | 640 | -1 | 0.70 | 300 | 100 | 0.899 | 0.308 | 0.599 | 0.529 |
| runx2 | yolo26x | warehouse-bb | 640 | -1 | 0.70 | 300 | 100 | 0.951 | 0.336 | 0.638 | 0.547 |
| yolo26s_12804 | yolo26s | warehouse-bb-4 | 1280 | -1 | 0.70 | 300 | 100 | 0.892 | 0.419 | 0.654 | 0.553 |
| yolo26x_12802 | yolo26x | warehouse-bb-4 | 1280 | -1 | 0.70 | 300 | 100 | 0.970 | 0.442 | 0.693 | 0.646 |

### Ablation Study
Cumulative impact of pipeline improvements on mAP50 and Recall.

| Configuration | mAP50 | Recall |
|---|---|---|
| No filter, 880 fr., 640 px (runx12) | 0.599 | 0.308 |
| Class filter, 880 fr., 1280 px (s_12804) | 0.654 | 0.419 |
| **Filter + 2,640 fr. + opt. settings (LAR1r)** | **0.735** | **0.697** |

**Key Observations:**
1. **Class filtering** is the single largest lever, raising recall from ~0.31 to ~0.70 (a 2.3x improvement).
2. **Dataset size beats model size.** yolo26l on 2,640 frames outperforms yolo26x on 880 frames.
3. **Higher IoU (0.85)** improves box quality without catastrophic recall loss.

### Final Best Model Performance (LAR1r)
| Metric | Value |
|---|---|
| Precision | 0.9191 |
| Recall | 0.6970 |
| **mAP @ IoU 0.50** | **0.7346** |
| **mAP @ IoU 0.50:0.95** | **0.6125** |
| Train box loss | 0.8083 |
| Val box loss | 0.7831 |
| Image size | 1280 px |
| Batch | 3 |
| IoU threshold | 0.85 |
| Saved weights | `lar1r.pt` |

## 5. Warehouse Object Category Aliases
- `box`, `boxes`, `carton` -> `box`
- `crate`, `crates` -> `crate`
- `rack`, `shelf` -> `rack`
- `bottle`, `bottles` -> `bottle`
- `sign`, `signs` -> `sign`
- `fire extinguisher`, `extinguisher` -> `extinguisher`
- `forklift`, `forklifts` -> `forklift`
- `barrel`, `barel`, `barrels` -> `barrel`
- `cone`, `cones` -> `cone`
- `pallet`, `pallets` -> `pallet`
- `fuse box`, `fuse_box` -> `fuse_box`
- `pillar`, `pillars` -> `pillar`
- `lamp`, `lamps` -> `lamp`
- `wire`, `wires` -> `wire`
- `cart`, `carts` -> `cart`
- `bucket`, `buckets` -> `bucket`
- `barcode`, `barcodes` -> `barcode`
