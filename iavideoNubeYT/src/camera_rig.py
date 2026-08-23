"""
camera_rig.py - Adaptive tracking camera with speed & FOV curves

Implements dynamic camera movement that automatically adjusts:
- Distance (Y-axis offset) based on target scale
- Height (Z-axis) for optimal framing
- Focal length to prevent clipping on large objects
- Smooth horizontal tracking along X-axis
"""

import bpy
import math
from mathutils import Vector


class AdaptiveCameraRig:
    """
    Adaptive camera rig for scale comparison videos.
    Automatically calculates optimal camera position based on object size.
    """
    
    def __init__(self, camera_name="MainCamera"):
        self.camera = bpy.data.objects.get(camera_name)
        if not self.camera:
            raise ValueError(f"Camera '{camera_name}' not found in scene")
        
        # Base parameters
        self.base_distance = 10.0  # Base Y distance for small objects
        self.base_height = 5.0     # Base Z height
        self.min_focal_length = 24.0
        self.max_focal_length = 85.0
        
        # Scale thresholds (meters)
        self.min_scale = 0.16   # Smallest object (e.g., drone)
        self.max_scale = 337.0  # Largest object (e.g., mountain)
        
        # Animation settings
        self.frames_per_object = 120  # 2 seconds at 60fps
        self.transition_frames = 30   # Smooth transition between objects
        
    def calculate_camera_distance(self, object_scale_m):
        """
        Calculate optimal camera distance based on object scale.
        Uses logarithmic scaling to handle wide range (0.16m to 337m).
        
        Args:
            object_scale_m: Object height in meters
            
        Returns:
            tuple: (distance_y, height_z, focal_length)
        """
        # Clamp scale to valid range
        scale = max(self.min_scale, min(self.max_scale, object_scale_m))
        
        # Logarithmic scaling factor (handles wide range smoothly)
        scale_ratio = math.log(scale / self.min_scale) / math.log(self.max_scale / self.min_scale)
        
        # Calculate distance with exponential curve
        # Small objects: closer camera, Large objects: farther camera
        distance_multiplier = 1.0 + (scale_ratio * 4.0)  # 1x to 5x base distance
        distance_y = self.base_distance * distance_multiplier
        
        # Height calculation: keep camera above object center
        # Higher for larger objects to show full scale
        height_multiplier = 0.5 + (scale_ratio * 0.8)  # 0.5x to 1.3x base height
        height_z = self.base_height * height_multiplier
        
        # Focal length adjustment
        # Wide angle for small objects, telephoto for large to reduce distortion
        focal_length = self.min_focal_length + (scale_ratio * (self.max_focal_length - self.min_focal_length))
        
        return distance_y, height_z, focal_length
    
    def calculate_horizontal_track(self, object_index, total_objects, track_width=15.0):
        """
        Calculate X-axis position for horizontal tracking shot.
        
        Args:
            object_index: Current object index (0-based)
            total_objects: Total number of objects
            track_width: Total width of camera track
            
        Returns:
            float: X position
        """
        if total_objects <= 1:
            return 0.0
        
        # Distribute objects across track width
        spacing = track_width / max(1, total_objects - 1)
        start_x = -track_width / 2
        
        return start_x + (object_index * spacing)
    
    def setup_keyframe(self, frame, location, rotation=None, focal_length=None):
        """
        Setup keyframe for camera at specific frame.
        
        Args:
            frame: Frame number
            location: Vector3 location
            rotation: Optional rotation Euler
            focal_length: Optional focal length in mm
        """
        self.camera.location = location
        
        if rotation:
            self.camera.rotation_euler = rotation
        
        if focal_length:
            self.camera.data.lens = focal_length
        
        # Insert keyframes for smooth interpolation
        self.camera.keyframe_insert(data_path="location", frame=frame)
        self.camera.keyframe_insert(data_path="rotation_euler", frame=frame)
        
        if focal_length:
            self.camera.data.keyframe_insert(data_path="lens", frame=frame)
    
    def animate_scale_comparison(self, objects_data, start_frame=1):
        """
        Animate camera moving through all objects in sequence.
        
        Args:
            objects_data: List of dicts with keys:
                - 'name': Object name
                - 'scale_m': Object height in meters
                - 'location': Vector3 location (optional, default (0,0,0))
            start_frame: Starting frame number
        """
        total_objects = len(objects_data)
        current_frame = start_frame
        
        print(f"\n{'='*50}")
        print(f"Setting up adaptive camera animation for {total_objects} objects")
        print(f"{'='*50}")
        
        for i, obj_data in enumerate(objects_data):
            obj_name = obj_data.get('name', f'Object_{i}')
            obj_scale = obj_data.get('scale_m', 1.0)
            obj_location = obj_data.get('location', Vector((0, 0, 0)))
            
            # Calculate optimal camera position
            distance_y, height_z, focal_length = self.calculate_camera_distance(obj_scale)
            track_x = self.calculate_horizontal_track(i, total_objects)
            
            # Camera looks at object from calculated position
            camera_location = Vector((
                obj_location.x + track_x,
                obj_location.y - distance_y,  # Behind object
                obj_location.z + height_z      # Above ground
            ))
            
            # Calculate rotation to look at object
            direction = obj_location - camera_location
            rotation = direction.to_track_quat('Z', 'Y').to_euler()
            
            # Setup keyframe at current position
            self.setup_keyframe(current_frame, camera_location, rotation, focal_length)
            
            print(f"  Frame {current_frame}: {obj_name} ({obj_scale}m)")
            print(f"    → Camera: {camera_location}")
            print(f"    → Focal: {focal_length:.1f}mm")
            
            # Move to next object
            current_frame += self.frames_per_object
            
            # Add transition frames if not last object
            if i < total_objects - 1:
                # Smooth interpolation handled by Blender's F-curves
                pass
        
        # Hold final frame
        hold_frames = 60
        self.setup_keyframe(current_frame + hold_frames, camera_location, rotation, focal_length)
        
        print(f"\n✓ Animation complete: {current_frame + hold_frames} total frames")
        print(f"{'='*50}\n")
        
        return current_frame + hold_frames
    
    def create_smooth_curves(self):
        """
        Apply smooth interpolation curves to camera keyframes.
        Creates professional ease-in/ease-out motion.
        """
        # Get all camera location F-curves
        for data_path in ["location", "rotation_euler"]:
            for idx in range(3):
                curve_path = f"{data_path}[{idx}]"
                try:
                    fcurve = self.camera.animation_data.action.fcurves.find(curve_path)
                    if fcurve:
                        # Set interpolation type
                        for kf in fcurve.keyframe_points:
                            kf.interpolation = 'BEZIER'
                            # Adjust handles for smooth easing
                            kf.handle_left_type = 'AUTO'
                            kf.handle_right_type = 'AUTO'
                except Exception as e:
                    print(f"Warning: Could not set curve for {curve_path}: {e}")
        
        print("✓ Applied smooth Bezier interpolation curves")
    
    def setup_depth_of_field(self, focus_distance=10.0, fstop=2.8):
        """
        Configure cinematic depth of field.
        
        Args:
            focus_distance: Distance to focus point in meters
            fstop: Aperture value (lower = more blur)
        """
        self.camera.data.dof.use_dof = True
        self.camera.data.dof.focus_distance = focus_distance
        self.camera.data.dof.aperture_fstop = fstop
        
        print(f"✓ Depth of field enabled (f/{fstop}, focus: {focus_distance}m)")


def create_camera_rig_from_scene():
    """
    Auto-detect objects in scene and create camera animation.
    """
    print("\n" + "="*50)
    print("Auto-detecting objects for camera rig setup")
    print("="*50)
    
    # Find all mesh objects (excluding floor, lights, text)
    objects_data = []
    
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and 'Floor' not in obj.name and 'Light' not in obj.name:
            # Estimate scale from bounding box
            bbox = obj.bound_box
            if bbox:
                # Calculate approximate height
                min_z = min(v[2] for v in bbox)
                max_z = max(v[2] for v in bbox)
                height = (max_z - min_z) * obj.scale[2]
                
                # Only include if reasonable size
                if height > 0.1:
                    objects_data.append({
                        'name': obj.name,
                        'scale_m': height,
                        'location': obj.location
                    })
    
    # Sort by scale (smallest to largest for dramatic effect)
    objects_data.sort(key=lambda x: x['scale_m'])
    
    if not objects_data:
        print("⚠ No suitable objects found in scene")
        return None
    
    print(f"Found {len(objects_data)} objects:")
    for obj in objects_data:
        print(f"  - {obj['name']}: {obj['scale_m']:.2f}m")
    
    # Create rig and animate
    try:
        rig = AdaptiveCameraRig()
        rig.animate_scale_comparison(objects_data)
        rig.create_smooth_curves()
        return rig
    except Exception as e:
        print(f"Error creating camera rig: {e}")
        return None


# Entry point for Blender execution
if __name__ == "__main__":
    import sys
    
    print("\n" + "="*50)
    print("Camera Rig Module - Adaptive Tracking System")
    print("="*50)
    
    # Try to auto-setup from scene
    rig = create_camera_rig_from_scene()
    
    if rig:
        print("\n✓ Camera rig successfully configured!")
        print("  Run render_pipeline.py to generate output.")
    else:
        print("\n⚠ Camera rig setup incomplete.")
        print("  Ensure objects are imported before running this script.")
