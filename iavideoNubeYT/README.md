# iavideoNubeYT - Automated 3D Scale Comparison Video Pipeline

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Blender 4.2+](https://img.shields.io/badge/blender-4.2+-orange.svg)](https://www.blender.org/download/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Fully automated, headless 3D scale comparison video production pipeline for YouTube** - Generate cinematic videos comparing objects from 0.16m to 337m with adaptive camera rigging, EEVEE Next rendering, and procedural audio.

## 🎯 Features

- **🤖 AI-Powered 3D Generation**: Microsoft TRELLIS integration for automatic image-to-3D conversion
- **🎬 Cinematic Camera Rigging**: Adaptive camera system that auto-calculates optimal framing for any scale
- **✨ EEVEE Next Rendering**: High-quality real-time rendering with bloom, shadows, and motion blur
- **🎵 Procedural Audio**: Auto-generated whooshes, clicks, and atmospheric drones synchronized to video
- **☁️ Cloud-Ready**: Docker container for GPU cloud deployment (RunPod, Lambda Labs, etc.)
- **📺 YouTube Optimized**: 1080p60 / 4K output targeting high RPM Tier-1 content

## 📁 Project Structure

```
iavideoNubeYT/
├── data/
│   └── military_vehicles.csv        # Ordered dataset (scale comparisons)
├── src/
│   ├── generate_models.py          # Batch 3D inference using TRELLIS
│   ├── build_scene.py              # Blender scene constructor & shaders
│   ├── camera_rig.py               # Adaptive tracking camera system
│   ├── render_pipeline.py          # Headless EEVEE Next rendering
│   └── generate_audio.py           # Procedural audio generation
├── assets/
│   ├── images/                     # Input 2D reference images
│   ├── models/                     # Output .glb 3D meshes
│   └── audio/                      # Generated SFX and ambience
├── output/
│   └── renders/                    # Final exported videos
├── Dockerfile                      # Cloud GPU deployment config
├── run_all.sh                      # One-click execution pipeline
└── requirements.txt                # Python dependencies
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Blender 4.2+** (for headless rendering)
- **FFmpeg** (for audio/video mixing)
- **NVIDIA GPU** (recommended for TRELLIS, CUDA 12.x)

### Installation

1. **Clone the repository:**
```bash
git clone https://github.com/Jhonhb16/iavideoNubeYT.git
cd iavideoNubeYT
```

2. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

3. **Install PyTorch with CUDA support:**
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

4. **Verify installation:**
```bash
python3 -c "import numpy, PIL, torch; print('✓ Dependencies OK')"
blender --version
ffmpeg -version
```

### One-Click Execution

```bash
./run_all.sh --resolution 1080p --quality high
```

**Options:**
- `--resolution`: `1080p` or `4K`
- `--quality`: `low`, `medium`, `high`, `ultra`
- `--skip-models`: Skip 3D generation (use existing models)
- `--skip-audio`: Skip audio generation

## 🎬 Pipeline Phases

### Phase 1: 3D Model Generation (`generate_models.py`)

Converts 2D reference images to 3D GLB models using Microsoft TRELLIS:

```bash
python3 src/generate_models.py \
    --csv data/military_vehicles.csv \
    --images-dir assets/images \
    --models-dir assets/models \
    --placeholders  # Use simple geometry if no GPU
```

**Input CSV format:**
```csv
order,name,scale_m,asset_file,label
1,soldier,1.8,soldier.glb,Soldier 1.8m
2,tank,10.2,tank.glb,Tank 10.2m
3,mountain,337.0,mountain.glb,Mountain 337m
```

### Phase 2: Scene Building (`build_scene.py`)

Creates cinematic Blender scene with:
- Dark reflective floor (roughness: 0.18)
- 3-point lighting system
- Floating 3D text labels

```bash
blender -b -P src/build_scene.py -- data/military_vehicles.csv
```

### Phase 3: Camera Rigging (`camera_rig.py`)

Adaptive camera system with logarithmic scaling:

| Object Scale | Camera Distance | Focal Length |
|-------------|-----------------|--------------|
| 0.16m (small) | 10m | 24mm (wide) |
| 10m (medium) | 30m | 50mm (normal) |
| 337m (large) | 50m | 85mm (telephoto) |

```bash
blender -b -P src/camera_rig.py
```

### Phase 4: Rendering (`render_pipeline.py`)

Headless EEVEE Next rendering with quality presets:

```bash
blender -b -P src/render_pipeline.py -- \
    --resolution 1080p \
    --quality high \
    --output output/renders
```

**EEVEE Next Settings (High Quality):**
- TAA Samples: 64
- Bloom: Enabled (threshold: 0.7)
- Shadows: 4096px cube
- Motion Blur: Enabled
- GTAO: Enabled

### Phase 5: Audio Generation (`generate_audio.py`)

Procedural audio synthesis:
- **Whooshes**: Frequency-swept tones for transitions
- **Clicks**: Mechanical UI sounds for markers
- **Drone**: Harmonic atmospheric background

```bash
python3 src/generate_audio.py \
    --duration 30 \
    --transitions "5,10,15,20,25" \
    --markers "0,5,10,15,20" \
    --output assets/audio
```

### Phase 6: Final Mix

Automatic audio-video multiplexing via FFmpeg:

```bash
python3 src/generate_audio.py \
    --mix-with-video output/renders/video.mp4 \
    --output-video output/renders/final.mp4
```

## 🐳 Docker Deployment

Build and run on cloud GPU (RunPod, Lambda Labs):

```bash
# Build Docker image
docker build -t iavideo-nube-yt .

# Run with GPU access
docker run --gpus all -v $(pwd)/output:/app/output iavideo-nube-yt \
    ./run_all.sh --resolution 4K --quality ultra
```

**RunPod Configuration:**
- Base Image: `nvidia/cuda:12.1.0-cudnn8-devel-ubuntu22.04`
- GPU: RTX 4090 / A100 (24GB+ VRAM recommended)
- Storage: 50GB+ for model cache and renders

## 🎨 Customization

### Adding New Scale Comparisons

1. Edit `data/military_vehicles.csv`:
```csv
order,name,scale_m,asset_file,label
6,aircraft_carrier,333.0,carrier.glb,USS Enterprise 333m
```

2. Add reference image to `assets/images/aircraft_carrier.png`

3. Run pipeline with `--skip-models` if using existing 3D assets

### Adjusting Camera Behavior

Modify `src/camera_rig.py` parameters:

```python
self.base_distance = 10.0   # Starting Y distance
self.base_height = 5.0      # Starting Z height
self.frames_per_object = 120  # 2 seconds at 60fps
```

### Audio Customization

Edit `src/generate_audio.py` for different sound profiles:

```python
# Deeper drone
generate_atmospheric_drone(base_freq=30.0, intensity="high")

# Faster whoosh
generate_whoosh(duration=1.0, direction="up")
```

## 📊 Performance Benchmarks

| Resolution | Quality | Render Time (per frame) | Total (300 frames) |
|-----------|---------|------------------------|-------------------|
| 1080p | High | ~2s | ~10 min |
| 4K | High | ~5s | ~25 min |
| 1080p | Ultra | ~4s | ~20 min |
| 4K | Ultra | ~10s | ~50 min |

*Tested on NVIDIA RTX 4090, EEVEE Next engine*

## 🔧 Troubleshooting

### Common Issues

**Blender not found:**
```bash
export PATH="/path/to/blender:$PATH"
# Or create symlink:
sudo ln -s /opt/blender/blender /usr/local/bin/blender
```

**TRELLIS import error:**
```bash
# Ensure PyTorch with CUDA is installed
pip uninstall torch torchvision
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

**FFmpeg audio mix fails:**
```bash
# Update FFmpeg to latest version
sudo apt-get update && sudo apt-get install ffmpeg
```

**GPU out of memory:**
- Reduce resolution to 1080p
- Lower quality preset to "medium"
- Reduce TAA samples in `render_pipeline.py`

## 📝 License

MIT License - See [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- **Microsoft TRELLIS**: Image-to-3D conversion
- **Blender Foundation**: EEVEE Next render engine
- **FFmpeg**: Audio/video processing

## 📬 Contact

For issues and feature requests, please open a GitHub issue.

---

**Built for YouTube automation at scale** 🎬🚀
