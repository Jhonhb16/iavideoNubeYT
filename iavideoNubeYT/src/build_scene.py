"""
build_scene.py - Blender headless scene constructor & shader setup

Creates a cinematic 3D comparison scene with:
- Dark reflective infinite floor with micro-roughness (0.18)
- High-contrast 3-point cinematic lighting
- Dynamic floating text markers for scale display
"""

import bpy
import math


def clear_scene():
    """Remove all existing objects from the scene."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


def create_floor():
    """Create dark reflective infinite floor with grid subdivisions."""
    # Create plane
    bpy.ops.mesh.primitive_plane_add(size=100, location=(0, 0, 0))
    floor = bpy.context.active_object
    floor.name = "Floor"
    
    # Scale to appear infinite
    floor.scale = (10, 10, 1)
    
    # Create material with dark reflective properties
    mat = bpy.data.materials.new(name="FloorMaterial")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    
    # Set dark color with micro-roughness
    bsdf.inputs["Base Color"].default_value = (0.05, 0.05, 0.08, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.18
    bsdf.inputs["Metallic"].default_value = 0.7
    
    # Add subtle emission for edge glow
    mat.node_tree.nodes.new(type="ShaderNodeEmission")
    emission = mat.node_tree.nodes["Emission"]
    emission.inputs["Color"].default_value = (0.1, 0.1, 0.15, 1.0)
    emission.inputs["Strength"].default_value = 0.3
    
    # Mix with Principled BSDF
    mix_shader = mat.node_tree.nodes.new(type="ShaderNodeMixShader")
    mix_shader.inputs["Fac"].default_value = 0.1
    mat.node_tree.links.new(emission.outputs["Emission"], mix_shader.inputs[1])
    mat.node_tree.links.new(bsdf.outputs["BSDF"], mix_shader.inputs[2])

    output_node = nodes.get("Material Output")
    mat.node_tree.links.new(mix_shader.outputs["Shader"], output_node.inputs["Surface"])
    
    floor.data.materials.append(mat)
    
    return floor


def create_three_point_lighting():
    """Setup high-contrast 3-point cinematic lighting system."""
    # Key light (Sun) - Main directional source
    bpy.ops.object.light_add(type='SUN', location=(10, -10, 15))
    sun = bpy.context.active_object
    sun.name = "KeyLight_Sun"
    sun.rotation_euler = (math.radians(60), 0, math.radians(45))
    sun.data.energy = 3.0
    sun.data.shadow_soft_size = 0.5
    
    # Fill light - Soft frontal illumination
    bpy.ops.object.light_add(type='AREA', location=(-5, 5, 8))
    fill = bpy.context.active_object
    fill.name = "FillLight"
    fill.rotation_euler = (math.radians(45), 0, math.radians(-30))
    fill.data.energy = 1.5
    fill.data.size = 5
    
    # Rim/Back light - Edge highlighting
    bpy.ops.object.light_add(type='SPOT', location=(0, -15, 10))
    rim = bpy.context.active_object
    rim.name = "RimLight"
    rim.rotation_euler = (math.radians(70), 0, 0)
    rim.data.energy = 2.0
    rim.data.spot_size = math.radians(45)
    
    return [sun, fill, rim]


def create_floating_text(text_content, location, scale=0.5):
    """Create dynamic 3D floating text marker with name and metric."""
    bpy.ops.object.text_add(location=location)
    text_obj = bpy.context.active_object
    text_obj.name = f"Text_{text_content.replace(' ', '_')}"
    
    text_data = text_obj.data
    text_data.body = text_content
    text_data.size = scale
    text_data.font = bpy.data.fonts.load("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    
    # Extrude for 3D effect
    text_data.extrude = 0.02
    text_data.bevel_depth = 0.01
    
    # Create glowing material
    mat = bpy.data.materials.new(name="TextMaterial")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    
    # Bright cyan/blue color
    bsdf.inputs["Base Color"].default_value = (0.2, 0.6, 1.0, 1.0)
    bsdf.inputs["Emission"].default_value = (0.3, 0.7, 1.0, 1.0)
    bsdf.inputs["Emission Strength"].default_value = 2.0
    
    text_obj.data.materials.append(mat)
    
    # Always face camera
    constraint = text_obj.constraints.new(type='TRACK_TO')
    constraint.target = None  # Will track camera in render
    constraint.track_axis = 'TRACK_NEGATIVE_Z'
    constraint.up_axis = 'UP_Y'
    
    return text_obj


def import_asset(asset_path, location, scale_factor=1.0):
    """Import GLB asset into scene at specified location."""
    try:
        bpy.ops.import_scene.gltf(filepath=asset_path)
        imported = bpy.context.selected_objects
        
        if imported:
            # Group all imported objects under empty parent
            parent = bpy.data.objects.new(f"Asset_{asset_path.split('/')[-1]}", None)
            bpy.context.collection.objects.link(parent)
            
            for obj in imported:
                obj.parent = parent
            
            parent.location = location
            parent.scale = (scale_factor, scale_factor, scale_factor)
            
            return parent
    except Exception as e:
        print(f"Warning: Could not import {asset_path}: {e}")
    
    return None


def setup_camera_for_comparison():
    """Configure camera settings for cinematic output."""
    # Remove default camera if exists
    if "Camera" in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects["Camera"])
    
    bpy.ops.object.camera_add(location=(0, -10, 5))
    camera = bpy.context.active_object
    camera.name = "MainCamera"
    camera.rotation_euler = (math.radians(75), 0, 0)
    
    # Camera settings for cinematic look
    camera.data.lens = 35  # Wide angle for scale perception
    camera.data.clip_end = 10000
    camera.data.dof.use_dof = False
    
    bpy.context.scene.camera = camera
    
    return camera


def configure_render_settings(resolution_x=1920, resolution_y=1080, fps=60):
    """Configure EEVEE Next render settings for high-quality output."""
    scene = bpy.context.scene
    
    # Render engine
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    
    # Resolution
    scene.render.resolution_x = resolution_x
    scene.render.resolution_y = resolution_y
    scene.render.resolution_percentage = 100
    
    # Frame rate
    scene.render.fps = fps
    
    # Output format
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    
    # EEVEE Next quality settings
    scene.eevee.taa_render_samples = 64
    scene.eevee.use_bloom = True
    scene.eevee.bloom_threshold = 0.8
    scene.eevee.bloom_knee = 0.5
    scene.eevee.bloom_intensity = 0.5
    
    # Shadows
    scene.eevee.use_shadows = True
    scene.eevee.shadow_cube_size = '4096'
    
    # Ambient occlusion
    scene.eevee.use_gtao = True
    scene.eevee.gtao_distance = 10.0
    
    return scene


def build_complete_scene(csv_data_path=None, output_timestamps_path=None):
    """Build complete comparison scene from CSV data with camera rig."""
    print("=" * 50)
    print("Building 3D Scale Comparison Scene")
    print("=" * 50)
    
    # Clear existing scene
    clear_scene()
    
    # Create environment
    floor = create_floor()
    lights = create_three_point_lighting()
    camera = setup_camera_for_comparison()
    
    # Configure render
    scene = configure_render_settings()
    
    print(f"✓ Floor created: {floor.name}")
    print(f"✓ Lighting setup: {[l.name for l in lights]}")
    print(f"✓ Camera configured: {camera.name}")
    
    # If CSV provided, import assets and setup camera rig
    if csv_data_path:
        import csv
        try:
            with open(csv_data_path, 'r') as f:
                reader = csv.DictReader(f)
                assets_imported = 0
                
                for row in reader:
                    asset_file = row.get('asset_file', '')
                    scale_m = float(row.get('scale_m', 1.0))
                    label = row.get('label', '')
                    
                    # Construct full path (assuming assets/models directory)
                    import os
                    asset_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                             'assets', 'models', asset_file)
                    
                    # Import asset
                    asset_obj = import_asset(asset_path, (0, 0, 0))
                    
                    if asset_obj:
                        # Create floating text above object
                        bbox_min = asset_obj.bound_box[0]
                        bbox_max = asset_obj.bound_box[6]
                        height = (bbox_max[2] - bbox_min[2]) * asset_obj.scale[2]
                        
                        text_pos = (0, 0, height + 2)
                        create_floating_text(label, text_pos, scale=0.5)
                        
                        assets_imported += 1
                        print(f"  ✓ Imported: {asset_file} ({label})")
                
                print(f"✓ Total assets imported: {assets_imported}")
        except Exception as e:
            print(f"Warning: Could not process CSV: {e}")
    
    # Setup camera rig with adaptive animation
    print("\n" + "="*50)
    print("Setting up adaptive camera rig...")
    print("="*50)
    
    import sys, os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))

    try:
        from .camera_rig import create_camera_rig_from_scene
    except ImportError:
        from camera_rig import create_camera_rig_from_scene
    
    # Default timestamps path
    if not output_timestamps_path:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_timestamps_path = os.path.join(os.path.dirname(script_dir), 'data', 'timestamps.json')
    
    rig = create_camera_rig_from_scene(timestamps_output_path=output_timestamps_path)
    
    if rig:
        print("✓ Camera rig animation configured!")
    else:
        print("⚠ Camera rig setup skipped")
    
    print("=" * 50)
    print("Scene build complete!")
    print("=" * 50)
    
    return {
        'floor': floor,
        'lights': lights,
        'camera': camera,
        'scene': scene,
        'rig': rig
    }


# Entry point for Blender execution
if __name__ == "__main__":
    import sys
    import os
    
    # Get CSV path from command line if provided
    csv_path = None
    timestamps_path = None
    
    if len(sys.argv) > 6:  # Blender passes arguments after --
        args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
        
        # Parse CSV path (first positional argument or --csv)
        if '--csv' in args:
            csv_idx = args.index('--csv')
            if csv_idx + 1 < len(args):
                csv_path = args[csv_idx + 1]
        elif len(args) > 0 and not args[0].startswith('--'):
            csv_path = args[0]
        
        # Parse timestamps path (--timestamps)
        if '--timestamps' in args:
            ts_idx = args.index('--timestamps')
            if ts_idx + 1 < len(args):
                timestamps_path = args[ts_idx + 1]
    
    # Default to data/military_vehicles.csv
    if not csv_path:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(os.path.dirname(script_dir), 'data', 'military_vehicles.csv')
    
    print(f"CSV data path: {csv_path}")
    print(f"Timestamps output path: {timestamps_path}")
    
    build_complete_scene(csv_path, timestamps_path)
