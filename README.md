# A-Ware: Multimodal Warehouse Intelligence System

A-Ware is a multimodal warehouse intelligence platform that combines synthetic data generation, YOLO-based object detection, Retrieval-Augmented Generation (RAG), and large language models to create an intelligent warehouse assistant capable of answering grounded natural-language inventory queries.


---

## Overview

A-Ware integrates:

- Synthetic warehouse data generation using NVIDIA Isaac Sim
- Multi-camera RGBD dataset creation
- YOLO26-based warehouse object detection
- ChromaDB-powered spatial RAG
- Gemini 3.1 Pro for natural-language reasoning
- Streamlit-based multimodal interface

The project creates a full pipeline from simulation to conversational warehouse intelligence.

---

## Key Features

- Synthetic multi-camera warehouse dataset generation
- 22 static cameras + 1 drone camera pipeline
- Automated annotation generation using Isaac Sim Replicator
- YOLO26-L object detection training pipeline
- Multi-image warehouse query support
- Spatial Retrieval-Augmented Generation (RAG)
- ChromaDB metadata indexing
- Gemini 3.1 Pro integration
- Exact inventory fact-layer retrieval
- Accumulative conversational query mode
- Streamlit-based dark-mode UI

---

## System Architecture

The system pipeline consists of five major stages:

1. Synthetic data generation in NVIDIA Isaac Sim
2. Automatic annotation generation and dataset preparation
3. YOLO26 training and benchmarking
4. Spatial metadata extraction and indexing
5. Multimodal warehouse intelligence application

The application combines:
- YOLO detections
- Warehouse spatial metadata
- ChromaDB semantic retrieval
- Gemini-based reasoning

to answer grounded warehouse inventory questions.

---

## Dataset Generation

### Simulator

- NVIDIA Isaac Sim
- USD-based warehouse environment
- omni.replicator.core for synchronized capture

### Camera Setup

- 22 static warehouse cameras
- 1 scripted drone camera
- Multi-view warehouse coverage

### Captured Modalities

Each frame contains:

- RGB image
- Bounding box annotations
- Instance segmentation
- Semantic segmentation
- Metric depth maps

### Dataset Variants

| Dataset | Frames | Classes |
|---|---|---|
| warehouse-bb | 880 | 28 |
| warehouse-bb-4 | 880 | 21 |
| masterwarehouse-2640 | 2640 | 21 |

### Structural Class Filtering

The pipeline removes structural classes such as:
- floor
- wall
- ceiling
- rack
- background

This improved recall by approximately 2.3×.

---

## YOLO26 Training

### Final Production Model

| Metric | Value |
|---|---|
| Model | YOLO26-L |
| Precision | 0.919 |
| Recall | 0.697 |
| mAP50 | 0.735 |
| mAP50-95 | 0.612 |
| Image Size | 1280 |
| Epochs | 100 |

### Training Improvements

Key optimizations:
- High-resolution training (1280px)
- Structural class filtering
- Larger dataset size
- Higher IoU threshold
- Drone-based aerial viewpoints

---

## A-Ware Application

The application supports:
- Text-only warehouse queries
- Image-based warehouse analysis
- Multi-image uploads
- Conversational inventory reasoning

### Example Queries

- "How many boxes are in Aisle 4?"
- "Show crates along with barrels"
- "Which aisle has the most items?"
- "Where are the fire extinguishers?"

---

## RAG Knowledge Base

### ChromaDB Metadata Index

The warehouse metadata contains:
- 2,754 indexed warehouse objects
- Spatial coordinates
- Rack and aisle mapping
- Shelf-level information
- Semantic text descriptions

### Two-Layer Retrieval Architecture

#### Fact Layer
Provides:
- exact inventory counts
- aisle summaries
- rack summaries
- shelf summaries

#### Document Layer
Provides:
- semantic retrieval
- object-level spatial reasoning
- contextual warehouse information

---

## Technologies Used

### AI / ML
- PyTorch
- Ultralytics YOLO
- Sentence Transformers
- Gemini 3.1 Pro

### Simulation
- NVIDIA Isaac Sim
- USD
- omni.replicator.core

### Backend
- Python
- ChromaDB
- Streamlit

### Embeddings
- all-MiniLM-L6-v2

---
---

## Project Archive & Resources

Complete project resources including:
- raw datasets
- processed datasets
- YOLO model weights
- demonstration videos
- additional files
- project materials

Google Drive Archive:

https://drive.google.com/drive/folders/1X2DTqPRzyYZypY-2txkBtzWPYZyk-N51?usp=sharing

## Repository Structure

```text
A-Ware-AI-System/
│
├── app/
│   ├── main.py
│   ├── engine.py
│
├── Python/
│   ├── Scripts/
│   ├── Models/
│
├── MDta/
│   ├── warehouse_rag_metadata_full.json
│
├── requirements.txt
├── README.md

