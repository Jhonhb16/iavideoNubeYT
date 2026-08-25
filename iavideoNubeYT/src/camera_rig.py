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
        self.frames_per_object = 120  # 2 seconds at 60fps (legacy / fallback)
        self.pause_frames = 108       # 1.8 seconds pause/focus per vehicle (legacy)
        self.transition_frames = 30   # Smooth transition between objects

        # Variable pacing: breaks the metronome effect of uniform timing.
        # Small objects move fast; large objects slow down and hold.
        # Tuned so a 15-object run lands around 56s (under the Shorts ceiling).
        self.min_travel_seconds = 1.2
        self.max_travel_seconds = 2.6
        self.min_hold_seconds = 0.6
        self.max_hold_seconds = 2.5
        # A scale jump of this ratio or more earns extra hold time
        self.jump_ratio_threshold = 1.8
        self.jump_bonus_seconds = 0.7
        
        # Timestamps for audio/motion graphics sync
        self.timestamps = {}
        
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
    
    def animate_scale_comparison(self, objects_data, start_frame=1, output_timestamps_path=None):
        """
        Animate camera moving through all objects in sequence.
        
        Args:
            objects_data: List of dicts with keys:
                - 'name': Object name
                - 'scale_m': Object height in meters
                - 'location': Vector3 location (optional, default (0,0,0))
            start_frame: Starting frame number
            output_timestamps_path: Optional path to save timestamps JSON
            
        Returns:
            int: Total frames rendered
        """
        total_objects = len(objects_data)
        current_frame = start_frame
        
        print(f"\n{'='*50}")
        print(f"Setting up adaptive camera animation for {total_objects} objects")
        print(f"{'='*50}")
        
        # Set dynamic clip range for extreme scale differences
        self.camera.data.clip_start = 0.05
        self.camera.data.clip_end = 5000
        print(f"  Camera clip range: {self.camera.data.clip_start}m - {self.camera.data.clip_end}m")
        
        fps = bpy.context.scene.render.fps

        # Pre-compute variable pacing: uniform timing (3.8s x 15 objects) reads
        # as a metronome and viewers predict the pattern by the third repeat.
        # Duration scales with object size, and a jump in scale earns extra hold.
        all_scales = [o.get('scale_m', 1.0) for o in objects_data]
        min_scale = min(all_scales) if all_scales else 1.0
        max_scale = max(all_scales) if all_scales else 1.0

        def pacing_for(index, scale_m):
            """Return (travel_frames, hold_frames) for this object."""
            import math

            # Log-normalised position in the scale range (0 = smallest, 1 = largest)
            if max_scale > min_scale:
                t = ((math.log10(max(scale_m, 0.01)) - math.log10(max(min_scale, 0.01)))
                     / (math.log10(max_scale) - math.log10(max(min_scale, 0.01))))
            else:
                t = 0.5
            t = max(0.0, min(1.0, t))

            # Travel: 1.5s for the smallest, up to 3.0s for the largest
            travel = int(fps * (self.min_travel_seconds
                                + t * (self.max_travel_seconds - self.min_travel_seconds)))

            # Hold: 0.8s baseline, up to 3.0s for the largest
            hold = int(fps * (self.min_hold_seconds
                              + t * (self.max_hold_seconds - self.min_hold_seconds)))

            # Bonus hold when this object is a big jump from the previous one
            if index > 0:
                prev = all_scales[index - 1]
                if prev > 0 and (scale_m / prev) >= self.jump_ratio_threshold:
                    hold += int(fps * self.jump_bonus_seconds)

            return travel, hold

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
            
            # Calculate timestamp in seconds
            timestamp_seconds = current_frame / fps
            self.timestamps[obj_name] = {
                'frame': current_frame,
                'timestamp': round(timestamp_seconds, 2),
                'scale_m': obj_scale,
                'focal_length_mm': round(focal_length, 1),
                'camera_distance': round(distance_y, 2),
                'camera_height': round(height_z, 2)
            }
            
            print(f"  Frame {current_frame} ({timestamp_seconds:.2f}s): {obj_name} ({obj_scale}m)")
            print(f"    → Camera: {camera_location}")
            print(f"    → Focal: {focal_length:.1f}mm")
            
            # Move to next object (variable pacing)
            travel_frames, hold_frames = pacing_for(i, obj_scale)
            self.timestamps[obj_name]['travel_frames'] = travel_frames
            self.timestamps[obj_name]['hold_frames'] = hold_frames

            current_frame += travel_frames

            # Hold/focus on this vehicle before moving on
            if i < total_objects - 1:
                pause_frame = current_frame + hold_frames
                self.setup_keyframe(pause_frame, camera_location, rotation, focal_length)
                print(f"    → Hold until frame {pause_frame} ({pause_frame/fps:.2f}s) "
                      f"[travel {travel_frames/fps:.2f}s, hold {hold_frames/fps:.2f}s]")
                current_frame = pause_frame
        
        # Hold final frame
        hold_frames = 60
        final_frame = current_frame + hold_frames
        self.setup_keyframe(final_frame, camera_location, rotation, focal_length)
        
        print(f"\n✓ Animation complete: {final_frame} total frames ({final_frame/fps:.2f}s)")
        
        # Export timestamps if path provided
        if output_timestamps_path:
            self.export_timestamps(output_timestamps_path)
        
        print(f"{'='*50}\n")
        
        return final_frame
    
    def export_timestamps(self, output_path):
        """Export timestamps to JSON file for audio/motion graphics sync."""
        import json
        
        output_data = {
            'timestamps': self.timestamps,
            'total_frames': max([t['frame'] for t in self.timestamps.values()]) if self.timestamps else 0,
            'fps': bpy.context.scene.render.fps,
            'duration_seconds': max([t['timestamp'] for t in self.timestamps.values()]) if self.timestamps else 0
        }
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"✓ Timestamps exported to: {output_path}")
        return output_path
    
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


def create_camera_rig_from_scene(timestamps_output_path=None):
    """
    Auto-detect objects in scene and create camera animation.
    
    Args:
        timestamps_output_path: Optional path to save timestamps JSON
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
        rig.animate_scale_comparison(objects_data, output_timestamps_path=timestamps_output_path)
        rig.create_smooth_curves()
        return rig
    except Exception as e:
        print(f"Error creating camera rig: {e}")
        return None


# Entry point for Blender execution
if __name__ == "__main__":
    import sys
    import os
    
    print("\n" + "="*50)
    print("Camera Rig Module - Adaptive Tracking System")
    print("="*50)
    
    # Get timestamps output path from command line or use default
    timestamps_path = None
    if len(sys.argv) > 6:
        try:
            idx = sys.argv.index('--timestamps')
            if idx + 1 < len(sys.argv):
                timestamps_path = sys.argv[idx + 1]
        except (ValueError, IndexError):
            pass
    
    # Default to data/timestamps.json
    if not timestamps_path:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        timestamps_path = os.path.join(os.path.dirname(script_dir), 'data', 'timestamps.json')
    
    print(f"Timestamps will be saved to: {timestamps_path}")
    
    # Try to auto-setup from scene
    rig = create_camera_rig_from_scene(timestamps_output_path=timestamps_path)
    
    if rig:
        print("\n✓ Camera rig successfully configured!")
        print("  Run render_pipeline.py to generate output.")
    else:
        print("\n⚠ Camera rig setup incomplete.")
        print("  Ensure objects are imported before running this script.")
