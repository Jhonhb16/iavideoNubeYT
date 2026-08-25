"""
render_pipeline.py - Batch headless EEVEE Next rendering script

Handles:
- Headless Blender execution for cloud deployment
- Batch rendering of all scale comparison sequences
- Output to 1080p60 / 4K MP4 format
- Error handling and progress tracking
"""

import bpy
import os
import sys
import subprocess
from pathlib import Path


def configure_output_settings(
    output_dir: str,
    resolution_x: int = 1920,
    resolution_y: int = 1080,
    fps: int = 60,
    format_type: str = 'FFMPEG'
):
    """
    Configure render output settings for video export.
    
    Args:
        output_dir: Directory for rendered output
        resolution_x: Width in pixels (1920 for 1080p, 3840 for 4K)
        resolution_y: Height in pixels (1080 for 1080p, 2160 for 4K)
        fps: Frames per second (60 for smooth motion)
        format_type: Output format ('PNG' for image sequence, 'FFMPEG' for direct MP4)
    """
    scene = bpy.context.scene
    
    # Resolution
    scene.render.resolution_x = resolution_x
    scene.render.resolution_y = resolution_y
    scene.render.resolution_percentage = 100
    
    # Frame rate
    scene.render.fps = fps
    scene.render.fps_base = 1.0
    
    # Output format
    scene.render.image_settings.file_format = format_type
    
    if format_type == 'FFMPEG':
        scene.render.ffmpeg.format = 'FFMPEG'
        scene.render.ffmpeg.codec = 'H264'
        scene.render.ffmpeg.audio_codec = 'AAC'
        
        # High quality H.264 settings
        scene.render.ffmpeg.video_bitrate = 50000  # 50 Mbps for high quality
        scene.render.ffmpeg.maxrate = 50000
        scene.render.ffmpeg.minrate = 30000
        scene.render.ffmpeg.buffersize = 1835
        scene.render.ffmpeg.gopsize = 30  # Keyframe interval
        
        # H.264 profile
        scene.render.ffmpeg.constant_rate_factor = 'LOW'  # CRF 18-23 equivalent
        
    # Set output path
    os.makedirs(output_dir, exist_ok=True)
    scene.render.filepath = os.path.join(output_dir, "scale_comparison_")
    
    print(f"✓ Output configured: {resolution_x}x{resolution_y} @ {fps}fps")
    print(f"  Format: {format_type}")
    print(f"  Directory: {output_dir}")


def setup_eevee_next_quality(preset: str = "high"):
    """
    Configure EEVEE Next render engine for maximum quality.
    
    Args:
        preset: Quality preset ("low", "medium", "high", "ultra")
    """
    scene = bpy.context.scene
    eevee = scene.eevee
    
    # Ensure EEVEE Next is active
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    
    if preset == "low":
        eevee.taa_render_samples = 16
        eevee.taa_time_samples = 8
        shadow_size = '1024'
    elif preset == "medium":
        eevee.taa_render_samples = 32
        eevee.taa_time_samples = 16
        shadow_size = '2048'
    elif preset == "high":
        eevee.taa_render_samples = 64
        eevee.taa_time_samples = 32
        shadow_size = '4096'
    else:  # ultra
        eevee.taa_render_samples = 128
        eevee.taa_time_samples = 64
        shadow_size = '8192'
    
    # Enable all quality features
    eevee.use_bloom = True
    eevee.bloom_threshold = 0.7
    eevee.bloom_knee = 0.5
    eevee.bloom_intensity = 0.6
    eevee.bloom_color = (1.0, 1.0, 1.0)
    
    # Shadows
    eevee.use_shadows = True
    eevee.shadow_cube_size = shadow_size
    eevee.shadow_high_bitdepth = True
    
    # Screen Space Reflections
    eevee.use_ssr = True
    eevee.ssr_thickness = 0.1
    eevee.ssr_max_roughness = 0.5
    
    # Ambient Occlusion
    eevee.use_gtao = True
    eevee.gtao_distance = 10.0
    eevee.gtao_factor = 1.5
    
    # Subsurface Scattering (for any translucent materials)
    eevee.use_sss = True
    eevee.sss_samples = 32
    
    # Motion blur for cinematic feel
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = 0.5
    
    print(f"✓ EEVEE Next configured: {preset} quality preset")
    print(f"  Samples: {eevee.taa_render_samples}")
    print(f"  Bloom: Enabled")
    print(f"  Shadows: {shadow_size}")
    print(f"  Motion Blur: Enabled")


def render_animation(output_dir: str, start_frame: int = 1, end_frame: int = None):
    """
    Render full animation sequence.
    
    Args:
        output_dir: Directory for rendered files
        start_frame: Starting frame number
        end_frame: Ending frame number (None for scene default)
    
    Returns:
        bool: True if successful, False otherwise
    """
    scene = bpy.context.scene
    
    # Set frame range
    scene.frame_start = start_frame
    if end_frame:
        scene.frame_end = end_frame
    
    print(f"\n{'='*50}")
    print(f"Starting render: frames {start_frame}-{scene.frame_end}")
    print(f"{'='*50}\n")
    
    try:
        # Render animation
        bpy.ops.render.render(animation=True)
        
        print(f"\n✓ Render complete!")
        print(f"  Output: {output_dir}")
        return True
        
    except Exception as e:
        print(f"\n⚠ Render failed: {e}")
        return False


def render_to_image_sequence(
    output_dir: str,
    start_frame: int = 1,
    end_frame: int = None,
    format_type: str = 'PNG'
) -> bool:
    """
    Render animation as image sequence (more reliable for long renders).
    
    Args:
        output_dir: Directory for image sequence
        start_frame: Starting frame
        end_frame: Ending frame
        format_type: Image format ('PNG', 'JPEG', 'OPEN_EXR')
    
    Returns:
        bool: Success status
    """
    scene = bpy.context.scene
    
    # Configure for image sequence
    scene.render.image_settings.file_format = format_type
    
    if format_type == 'PNG':
        scene.render.image_settings.color_mode = 'RGBA'
        scene.render.image_settings.compression = 15
    elif format_type == 'JPEG':
        scene.render.image_settings.color_mode = 'RGB'
        scene.render.image_settings.quality = 95
    elif format_type == 'OPEN_EXR':
        scene.render.image_settings.color_mode = 'RGBA'
        scene.render.image_settings.exr_codec = 'ZIP'
    
    # Set frame range
    scene.frame_start = start_frame
    if end_frame:
        scene.frame_end = end_frame
    
    # Setup output path with frame placeholder
    os.makedirs(output_dir, exist_ok=True)
    base_path = os.path.join(output_dir, "frame_####")
    scene.render.filepath = base_path
    
    print(f"\n{'='*50}")
    print(f"Rendering image sequence: {format_type}")
    print(f"Frames: {start_frame}-{scene.frame_end}")
    print(f"Output: {output_dir}/frame_XXXX.{format_type.lower()}")
    print(f"{'='*50}\n")
    
    try:
        bpy.ops.render.render(animation=True)
        print(f"\n✓ Image sequence render complete!")
        return True
    except Exception as e:
        print(f"\n⚠ Render failed: {e}")
        return False


def convert_sequence_to_video(
    sequence_dir: str,
    output_path: str,
    fps: int = 60,
    resolution: tuple = (1920, 1080),
    crf: int = 18
) -> bool:
    """
    Convert image sequence to MP4 using FFmpeg.
    
    Args:
        sequence_dir: Directory containing image sequence
        output_path: Full path for output MP4 file
        fps: Frame rate
        resolution: (width, height) tuple
        crf: Constant Rate Factor (18-28, lower=better quality)
    
    Returns:
        bool: Success status
    """
    try:
        # Find first image to determine format
        images = [f for f in os.listdir(sequence_dir) if f.startswith('frame_')]
        if not images:
            print(f"⚠ No images found in {sequence_dir}")
            return False
        
        # Sort to get pattern
        images.sort()
        sample_image = images[0]
        
        # Determine frame pattern
        # Assuming format: frame_0001.PNG
        frame_pattern = "frame_%04d." + sample_image.split('.')[-1]
        
        # FFmpeg command
        cmd = [
            'ffmpeg', '-y',  # Overwrite output
            '-framerate', str(fps),
            '-i', os.path.join(sequence_dir, frame_pattern),
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-crf', str(crf),
            '-preset', 'slow',
            '-c:a', 'aac',
            '-b:a', '192k',
            output_path
        ]
        
        print(f"\nConverting sequence to video...")
        print(f"  Input: {sequence_dir}/{frame_pattern}")
        print(f"  Output: {output_path}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✓ Video created: {output_path}")
            return True
        else:
            print(f"⚠ FFmpeg error: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"⚠ Conversion error: {e}")
        return False


def run_full_pipeline(
    blend_file: str = None,
    output_dir: str = "./output/renders",
    resolution: str = "1080p",
    quality: str = "high",
    use_sequence: bool = True
) -> bool:
    """
    Run complete rendering pipeline from scene setup to final video.
    
    Args:
        blend_file: Optional .blend file to load (None for current scene)
        output_dir: Output directory for renders
        resolution: "1080p" or "4K"
        quality: "low", "medium", "high", "ultra"
        use_sequence: If True, render image sequence then convert (more reliable)
    
    Returns:
        bool: Overall success status
    """
    print("\n" + "="*60)
    print("SCALE COMPARISON VIDEO - RENDER PIPELINE")
    print("="*60)
    
    # Resolve resolution
    if resolution == "4K":
        res_x, res_y = 3840, 2160
    else:  # 1080p default
        res_x, res_y = 1920, 1080
    
    # Load blend file if specified
    if blend_file and os.path.exists(blend_file):
        print(f"\nLoading scene: {blend_file}")
        bpy.ops.wm.open_mainfile(filepath=blend_file)
    
    # Configure quality
    setup_eevee_next_quality(quality)
    
    # Get frame count from camera animation if available
    scene = bpy.context.scene
    start_frame = scene.frame_start
    end_frame = scene.frame_end
    
    # Check if camera has animation
    camera = scene.camera
    if camera and camera.animation_data and camera.animation_data.action:
        action = camera.animation_data.action
        location_curve = action.fcurves.find('location')
        if location_curve:
            end_frame = int(location_curve.range[1] or end_frame)
    
    print(f"\nScene info:")
    print(f"  Resolution: {res_x}x{res_y} ({resolution})")
    print(f"  Frame range: {start_frame}-{end_frame}")
    print(f"  Total frames: {end_frame - start_frame + 1}")
    print(f"  Duration: {(end_frame - start_frame + 1) / 60:.1f}s @ 60fps")
    
    if use_sequence:
        # Render as image sequence
        sequence_dir = os.path.join(output_dir, "temp_sequence")
        success = render_to_image_sequence(sequence_dir, start_frame, end_frame, 'PNG')
        
        if success:
            # Convert to video
            os.makedirs(output_dir, exist_ok=True)
            timestamp = bpy.path.clean_name(f"scale_comparison_{resolution}_{quality}")
            output_video = os.path.join(output_dir, f"{timestamp}.mp4")
            
            success = convert_sequence_to_video(
                sequence_dir,
                output_video,
                fps=60,
                resolution=(res_x, res_y),
                crf=18
            )
            
            # Cleanup sequence if successful
            if success:
                print(f"\n✓ Final video: {output_video}")
                # Optional: remove temp sequence
                # shutil.rmtree(sequence_dir)
    else:
        # Direct video render
        configure_output_settings(output_dir, res_x, res_y, 60, 'FFMPEG')
        success = render_animation(output_dir, start_frame, end_frame)
    
    print("\n" + "="*60)
    if success:
        print("✓ RENDER PIPELINE COMPLETE")
    else:
        print("⚠ RENDER PIPELINE FAILED")
    print("="*60 + "\n")
    
    return success


# Entry point for Blender execution
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Render scale comparison video")
    parser.add_argument("--blend", type=str, help="Path to .blend scene file")
    parser.add_argument("--output", type=str, default="./output/renders",
                       help="Output directory for renders")
    parser.add_argument("--resolution", type=str, default="1080p",
                       choices=["1080p", "4K"], help="Output resolution")
    parser.add_argument("--quality", type=str, default="high",
                       choices=["low", "medium", "high", "ultra"],
                       help="Render quality preset")
    parser.add_argument("--direct", action="store_true",
                       help="Render directly to video (not image sequence)")
    
    args = parser.parse_args()
    
    # Get script directory for relative paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)
    
    output_dir = args.output if os.path.isabs(args.output) else os.path.join(base_dir, args.output)
    
    # Run pipeline
    success = run_full_pipeline(
        blend_file=args.blend,
        output_dir=output_dir,
        resolution=args.resolution,
        quality=args.quality,
        use_sequence=not args.direct
    )
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)
