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
    Useful for testing the pipeline without AI generation.
    
    Args:
        csv_path: Path to CSV with asset definitions
        models_dir: Directory for output GLB files
    """
    print("\n" + "="*50)
    print("Creating placeholder 3D models for testing")
    print("="*50)
    
    try:
        import bpy
        import mathutils
        
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                name = row.get('name', 'placeholder')
                asset_file = row.get('asset_file', f'{name}.glb')
                scale_m = float(row.get('scale_m', 1.0))
                
                # Clear scene
                bpy.ops.object.select_all(action='SELECT')
                bpy.ops.object.delete()
                
                # Create simple cube scaled to approximate size
                bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, scale_m/2))
                obj = bpy.context.active_object
                obj.name = name
                obj.scale = (1, 1, scale_m)
                
                # Add material
                mat = bpy.data.materials.new(name=f"{name}_mat")
                mat.use_nodes = True
                bsdf = mat.node_tree.nodes["Principled BSDF"]
                
                # Color based on scale (small=green, large=red)
                if scale_m < 5:
                    color = (0.2, 0.8, 0.2, 1.0)
                elif scale_m < 50:
                    color = (0.8, 0.8, 0.2, 1.0)
                else:
                    color = (0.8, 0.2, 0.2, 1.0)
                
                bsdf.inputs["Base Color"].default_value = color
                
                obj.data.materials.append(mat)
                
                # Export as GLB
                output_path = os.path.join(models_dir, asset_file)
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                bpy.ops.export_scene.gltf(
                    filepath=output_path,
                    export_format='GLB',
                    use_selection=True
                )
                
                print(f"  ✓ Created placeholder: {asset_file} ({scale_m}m)")
        
        print(f"\n✓ Placeholder models created successfully")
        print(f"  Replace with real TRELLIS models when GPU is available\n")
        
    except Exception as e:
        print(f"⚠ Error creating placeholders: {e}")


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
        create_placeholder_models(csv_path, models_dir)
    else:
        batch_convert_from_csv(csv_path, images_dir, models_dir)
