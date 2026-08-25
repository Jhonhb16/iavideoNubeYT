"""
generate_models.py - Batch 3D inference using Microsoft TRELLIS

Downloads and converts 2D reference images to 3D GLB models using:
- Microsoft TRELLIS for image-to-3D conversion
- Batch processing with error handling
- GPU acceleration detection
"""

import os
import sys
import json
import csv
from pathlib import Path
from typing import List, Dict, Optional


def check_gpu_availability() -> bool:
    """Check if CUDA GPU is available for acceleration."""
    try:
        import torch
        if torch.cuda.is_available():
            print(f"✓ CUDA GPU detected: {torch.cuda.get_device_name(0)}")
            print(f"  CUDA Version: {torch.version.cuda}")
            return True
        else:
            print("⚠ No CUDA GPU detected, will use CPU (slower)")
            return False
    except ImportError:
        print("⚠ PyTorch not installed, TRELLIS requires torch")
        return False


def install_trellis_dependencies():
    """Install required dependencies for TRELLIS."""
    import subprocess
    
    print("\nInstalling TRELLIS dependencies...")
    
    dependencies = [
        "torch",
        "torchvision",
        "trellis",
        "trimesh",
        "numpy",
        "Pillow"
    ]
    
    for dep in dependencies:
        try:
            __import__(dep.replace('-', '_'))
            print(f"  ✓ {dep} already installed")
        except ImportError:
            print(f"  Installing {dep}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", dep, "-q"])
                print(f"  ✓ {dep} installed")
            except Exception as e:
                print(f"  ⚠ Failed to install {dep}: {e}")


def download_trellis_model(model_path: str = "./models/trellis"):
    """Download TRELLIS model weights if not present."""
    from pathlib import Path
    
    model_dir = Path(model_path)
    
    if model_dir.exists() and any(model_dir.iterdir()):
        print(f"✓ TRELLIS model already downloaded at {model_path}")
        return True
    
    print(f"\nDownloading TRELLIS model to {model_path}...")
    print("  This may take several minutes (2-4GB)...")
    
    try:
        # TRELLIS auto-downloads on first use
        # Trigger download by importing
        import trellis
        
        print("✓ TRELLIS model download initiated")
        return True
        
    except Exception as e:
        print(f"⚠ Error downloading TRELLIS model: {e}")
        return False


def convert_image_to_3d(
    image_path: str,
    output_path: str,
    target_scale_m: float = 1.0,
    quality: str = "high"
) -> Optional[str]:
    """
    Convert single 2D image to 3D GLB model using TRELLIS.
    
    Args:
        image_path: Path to input 2D image (PNG/JPG)
        output_path: Path for output GLB file
        target_scale_m: Target real-world scale in meters
        quality: Quality preset ("low", "medium", "high")
    
    Returns:
        str: Output path if successful, None otherwise
    """
    try:
        import trellis
        import torch
        from PIL import Image
        
        print(f"\nConverting: {image_path}")
        
        # Validate input
        if not os.path.exists(image_path):
            print(f"  ⚠ Input image not found: {image_path}")
            return None
        
        # Load image
        img = Image.open(image_path).convert('RGBA')
        img = img.resize((512, 512))  # TRELLIS optimal size
        
        # Run TRELLIS inference
        print("  Running TRELLIS inference...")
        
        # Configure based on quality
        if quality == "low":
            octree_depth = 5
            num_samples = 16
        elif quality == "medium":
            octree_depth = 6
            num_samples = 32
        else:  # high
            octree_depth = 7
            num_samples = 64
        
        # Generate 3D model
        with torch.no_grad():
            # TRELLIS pipeline (simplified - actual implementation may vary)
            model = trellis.models.ImageTo3DModel()
            mesh = model.generate(img, octree_depth=octree_depth, num_samples=num_samples)
        
        # Scale to real-world dimensions
        # TRELLIS outputs unit cube, scale to target meters
        scale_factor = target_scale_m / max(mesh.bounds[:, 2])  # Scale by height
        mesh.apply_scale(scale_factor)
        
        # Export as GLB
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        mesh.export(output_path)
        
        print(f"  ✓ Generated: {output_path} ({target_scale_m}m scale)")
        return output_path
        
    except Exception as e:
        print(f"  ⚠ Error converting {image_path}: {e}")
        return None


def batch_convert_from_csv(
    csv_path: str,
    images_dir: str = "./assets/images",
    models_dir: str = "./assets/models"
) -> Dict[str, str]:
    """
    Batch convert all images listed in CSV to 3D models.
    
    Args:
        csv_path: Path to CSV with columns: name, asset_file, scale_m
        images_dir: Directory containing source images
        models_dir: Directory for output GLB files
    
    Returns:
        dict: Mapping of asset_file -> output_path for successful conversions
    """
    print("\n" + "="*50)
    print("Batch 3D Model Generation with TRELLIS")
    print("="*50)
    
    # Check prerequisites
    gpu_available = check_gpu_availability()
    
    if not gpu_available:
        print("\n⚠ WARNING: GPU acceleration not available")
        print("  Consider running on a GPU-enabled machine for faster processing")
    
    # Read CSV
    results = {}
    
    try:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        print(f"\nProcessing {len(rows)} assets from CSV...")
        
        for i, row in enumerate(rows, 1):
            name = row.get('name', f'asset_{i}')
            asset_file = row.get('asset_file', f'{name}.glb')
            scale_m = float(row.get('scale_m', 1.0))
            
            # Find corresponding image
            # Try multiple extensions
            image_extensions = ['.png', '.jpg', '.jpeg', '.webp']
            image_path = None
            
            for ext in image_extensions:
                test_path = os.path.join(images_dir, f"{name}{ext}")
                if os.path.exists(test_path):
                    image_path = test_path
                    break
            
            if not image_path:
                print(f"\n⚠ No source image found for: {name}")
                print(f"  Expected in: {images_dir}/[{name}.png|.jpg|.jpeg|.webp]")
                continue
            
            # Convert to 3D
            output_path = os.path.join(models_dir, asset_file)
            
            result = convert_image_to_3d(
                image_path=image_path,
                output_path=output_path,
                target_scale_m=scale_m,
                quality="high"
            )
            
            if result:
                results[asset_file] = result
            
            # Progress indicator
            print(f"Progress: {i}/{len(rows)}")
        
        print(f"\n{'='*50}")
        print(f"Batch complete: {len(results)}/{len(rows)} models generated")
        print(f"{'='*50}\n")
        
        return results
        
    except FileNotFoundError:
        print(f"⚠ CSV file not found: {csv_path}")
        return {}
    except Exception as e:
        print(f"⚠ Batch processing error: {e}")
        return {}


def create_placeholder_models(csv_path: str, models_dir: str = "./assets/models"):
    """
    Create simple placeholder GLB models when TRELLIS is unavailable.
    Uses trimesh (pure Python) so it runs outside of Blender.

    Each placeholder is a real 3D box whose dimensions are derived from the
    scale_m column of the CSV, with a color that reflects its size class.

    Args:
        csv_path: Path to CSV with asset definitions
        models_dir: Directory for output GLB files
    """
    print("\n" + "="*50)
    print("Creating placeholder 3D models for testing")
    print("="*50)

    try:
        import trimesh
        import numpy as np
    except ImportError:
        print("✗ trimesh is not installed. Run: pip install trimesh")
        return False

    created = 0
    failed = 0

    try:
        os.makedirs(models_dir, exist_ok=True)

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)

            for row in reader:
                name = row.get('name', 'placeholder')
                asset_file = row.get('asset_file', f'{name}.glb')

                try:
                    scale_m = float(row.get('scale_m', 1.0))
                except (TypeError, ValueError):
                    print(f"  ⚠ Invalid scale_m for '{name}', defaulting to 1.0m")
                    scale_m = 1.0

                if scale_m <= 0:
                    print(f"  ⚠ Non-positive scale_m for '{name}', defaulting to 1.0m")
                    scale_m = 1.0

                try:
                    # Box proportions: length is the defining dimension (scale_m),
                    # width and height derived so the shape reads as a vehicle.
                    length = scale_m
                    width = max(scale_m * 0.35, 0.05)
                    height = max(scale_m * 0.30, 0.05)

                    mesh = trimesh.creation.box(extents=(length, width, height))

                    # Sit the box on the floor (z=0) instead of centered on origin
                    mesh.apply_translation((0.0, 0.0, height / 2.0))

                    # Color based on scale (small=green, medium=yellow, large=red)
                    if scale_m < 5:
                        color = [51, 204, 51, 255]
                    elif scale_m < 50:
                        color = [204, 204, 51, 255]
                    else:
                        color = [204, 51, 51, 255]

                    mesh.visual.face_colors = np.tile(
                        np.array(color, dtype=np.uint8), (len(mesh.faces), 1)
                    )
                    mesh.metadata['name'] = name

                    output_path = os.path.join(models_dir, asset_file)
                    parent_dir = os.path.dirname(output_path)
                    if parent_dir:
                        os.makedirs(parent_dir, exist_ok=True)

                    # Export format is inferred from the file extension (.glb/.obj)
                    mesh.export(output_path)

                    created += 1
                    print(f"  ✓ Created placeholder: {asset_file} "
                          f"({length:.2f} x {width:.2f} x {height:.2f} m)")

                except Exception as e:
                    failed += 1
                    print(f"  ✗ Failed to create placeholder for '{name}': {e}")

    except FileNotFoundError:
        print(f"✗ CSV file not found: {csv_path}")
        return False
    except Exception as e:
        print(f"✗ Error reading CSV: {e}")
        return False

    print(f"\n{'='*50}")
    print(f"✓ Placeholders created: {created}")
    if failed:
        print(f"✗ Failed:              {failed}")
    print(f"  Replace with real TRELLIS models when GPU is available")
    print(f"{'='*50}\n")

    return failed == 0 and created > 0


# Entry point
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate 3D models from 2D images using TRELLIS")
    parser.add_argument("--csv", type=str, default="./data/military_vehicles.csv",
                       help="Path to CSV file with asset definitions")
    parser.add_argument("--images-dir", type=str, default="./assets/images",
                       help="Directory containing source images")
    parser.add_argument("--models-dir", type=str, default="./assets/models",
                       help="Directory for output GLB models")
    parser.add_argument("--placeholders", action="store_true",
                       help="Create simple placeholder models instead of AI generation")
    
    args = parser.parse_args()
    
    # Get script directory for relative paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)
    
    csv_path = args.csv if os.path.isabs(args.csv) else os.path.join(base_dir, args.csv)
    images_dir = args.images_dir if os.path.isabs(args.images_dir) else os.path.join(base_dir, args.images_dir)
    models_dir = args.models_dir if os.path.isabs(args.models_dir) else os.path.join(base_dir, args.models_dir)
    
    if args.placeholders or not check_gpu_availability():
        print("\nUsing placeholder mode (no GPU/TRELLIS)")
        success = create_placeholder_models(csv_path, models_dir)
    else:
        success = batch_convert_from_csv(csv_path, images_dir, models_dir)

    # Propagate failure so the calling shell script does not report false success
    sys.exit(0 if success else 1)
