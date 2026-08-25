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
import shutil

# 30 fps por defecto: los movimientos de camara son lentos y las pausas
# largas, asi que 60 fps duplica el coste de render sin ganancia visible.
# En un video de 8 minutos son 14.400 fotogramas en vez de 28.800.
DEFAULT_FPS = int(os.environ.get('IAVIDEO_FPS', '30'))
import subprocess
from pathlib import Path


def configure_output_settings(
    output_dir: str,
    resolution_x: int = 1920,
    resolution_y: int = 1080,
    fps: int = None,
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
    fps = DEFAULT_FPS if fps is None else fps
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


def setup_color_management(look: str = "AgX - Punchy", exposure: float = 0.3,
                           gamma: float = 1.05):
    """
    Configure color management for a punchy, high-contrast look.

    Blender 4.x defaults to the AgX view transform, which is filmic and
    intentionally desaturated. That reads as flat on a YouTube feed, so we
    apply a punchier look with a slight exposure lift.

    Args:
        look: Contrast look name (e.g. "AgX - Punchy", "AgX - High Contrast")
        exposure: Exposure offset in stops
        gamma: Gamma adjustment
    """
    scene = bpy.context.scene
    vs = scene.view_settings

    # Look names vary between Blender versions; fall back gracefully.
    applied_look = None
    for candidate in (look, "AgX - Punchy", "AgX - High Contrast", "Punchy", "None"):
        try:
            vs.look = candidate
            applied_look = candidate
            break
        except (TypeError, AttributeError):
            continue

    try:
        vs.exposure = exposure
        vs.gamma = gamma
    except AttributeError:
        pass

    try:
        scene.display_settings.display_device = 'sRGB'
    except (TypeError, AttributeError):
        pass

    print(f"✓ Color management: view_transform={getattr(vs, 'view_transform', '?')}, "
          f"look={applied_look}, exposure={exposure}")


def setup_cinematic_compositor(glow_threshold: float = 0.85,
                               glow_size: int = 8,
                               glow_mix: float = -0.75,
                               enable_streaks: bool = True):
    """
    Build a compositor node tree that restores the cinematic bloom look.

    EEVEE Next (Blender 4.2) removed the built-in bloom pass; the equivalent
    is now done in the compositor with a Glare node in FOG_GLOW mode.
    A second Glare in STREAKS mode adds anamorphic flares.

    Args:
        glow_threshold: Brightness above which the glow kicks in
        glow_size: Glow radius (larger = softer, more diffuse)
        glow_mix: Blend factor. Negative values mix subtly over the original.
        enable_streaks: Add an anamorphic streak pass on top of the fog glow
    """
    scene = bpy.context.scene
    scene.use_nodes = True
    tree = scene.node_tree

    # Start from a clean tree so repeated runs don't stack duplicate nodes
    tree.nodes.clear()

    render_layers = tree.nodes.new('CompositorNodeRLayers')
    render_layers.location = (-400, 0)

    composite = tree.nodes.new('CompositorNodeComposite')
    composite.location = (600, 0)

    last_output = render_layers.outputs['Image']

    # Fog glow: the bloom replacement
    try:
        fog = tree.nodes.new('CompositorNodeGlare')
        fog.location = (-100, 0)
        fog.glare_type = 'FOG_GLOW'
        fog.quality = 'HIGH'
        fog.threshold = glow_threshold
        fog.size = glow_size
        fog.mix = glow_mix
        tree.links.new(last_output, fog.inputs['Image'])
        last_output = fog.outputs['Image']
        print("  ✓ Glare FOG_GLOW (bloom replacement)")
    except (TypeError, AttributeError, KeyError) as e:
        print(f"  ⚠ Could not add FOG_GLOW glare: {e}")

    # Anamorphic streaks for a more expensive-looking image
    if enable_streaks:
        try:
            streaks = tree.nodes.new('CompositorNodeGlare')
            streaks.location = (150, -200)
            streaks.glare_type = 'STREAKS'
            streaks.quality = 'HIGH'
            streaks.threshold = 0.95
            streaks.streaks = 4
            streaks.mix = -0.85
            tree.links.new(last_output, streaks.inputs['Image'])
            last_output = streaks.outputs['Image']
            print("  ✓ Glare STREAKS (anamorphic flares)")
        except (TypeError, AttributeError, KeyError) as e:
            print(f"  ⚠ Could not add STREAKS glare: {e}")

    tree.links.new(last_output, composite.inputs['Image'])
    print("✓ Cinematic compositor configured")



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
        render_samples, time_samples = 16, 8
        shadow_size = '1024'
    elif preset == "medium":
        render_samples, time_samples = 32, 16
        shadow_size = '2048'
    elif preset == "high":
        render_samples, time_samples = 64, 32
        shadow_size = '4096'
    else:  # ultra
        render_samples, time_samples = 128, 64
        shadow_size = '8192'

    # Blender 4.2 EEVEE Next removed/renamed several legacy EEVEE properties.
    # Guard each assignment so the pipeline stays compatible across versions.
    def set_if_exists(obj, attr, value):
        """Assign attr only when the property exists on this Blender version."""
        if hasattr(obj, attr):
            setattr(obj, attr, value)
            return True
        return False

    # Sampling
    set_if_exists(eevee, 'taa_render_samples', render_samples)
    set_if_exists(eevee, 'taa_time_samples', time_samples)

    # Bloom (removed in EEVEE Next 4.2 - moved to the compositor)
    if set_if_exists(eevee, 'use_bloom', True):
        set_if_exists(eevee, 'bloom_threshold', 0.7)
        set_if_exists(eevee, 'bloom_knee', 0.5)
        set_if_exists(eevee, 'bloom_intensity', 0.6)
        set_if_exists(eevee, 'bloom_color', (1.0, 1.0, 1.0))

    # Shadows
    set_if_exists(eevee, 'use_shadows', True)
    set_if_exists(eevee, 'shadow_cube_size', shadow_size)
    set_if_exists(eevee, 'shadow_high_bitdepth', True)

    # Screen Space Reflections (replaced by raytracing in EEVEE Next)
    if set_if_exists(eevee, 'use_ssr', True):
        set_if_exists(eevee, 'ssr_thickness', 0.1)
        set_if_exists(eevee, 'ssr_max_roughness', 0.5)
    else:
        set_if_exists(eevee, 'use_raytracing', True)

    # Ambient Occlusion (folded into raytracing in EEVEE Next)
    if set_if_exists(eevee, 'use_gtao', True):
        set_if_exists(eevee, 'gtao_distance', 10.0)
        set_if_exists(eevee, 'gtao_factor', 1.5)

    # Subsurface Scattering (for any translucent materials)
    if set_if_exists(eevee, 'use_sss', True):
        set_if_exists(eevee, 'sss_samples', 32)

    # Motion blur for cinematic feel
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = 0.5

    actual_samples = getattr(eevee, 'taa_render_samples', render_samples)

    print(f"✓ EEVEE Next configured: {preset} quality preset")
    print(f"  Samples: {actual_samples}")
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


def _frame_path(output_dir: str, frame: int, format_type: str) -> str:
    """Exact on-disk path for a rendered frame (4-digit, matches the FFmpeg pattern)."""
    ext = {'PNG': 'png', 'JPEG': 'jpg', 'OPEN_EXR': 'exr'}.get(format_type, 'png')
    return os.path.join(output_dir, f"frame_{frame:04d}.{ext}")


def pending_frames(output_dir: str, start_frame: int, end_frame: int,
                   format_type: str = 'PNG', min_bytes: int = 1024) -> list:
    """
    Return the frames still needing a render.

    A frame counts as done only when its file exists AND is larger than
    min_bytes: a pod killed mid-write leaves a truncated file, and treating
    that as complete would bake a corrupt frame into the final video.
    """
    pending = []
    for f in range(start_frame, end_frame + 1):
        path = _frame_path(output_dir, f, format_type)
        try:
            if os.path.getsize(path) >= min_bytes:
                continue
        except OSError:
            pass
        pending.append(f)
    return pending


def setup_gpu_devices(prefer: str = None) -> dict:
    """
    Enable GPU compute devices for rendering.

    Blender headless does NOT pick up the GPU on its own: without this, a
    RunPod pod with a 4090 renders on CPU while still billing for the GPU.

    This only affects Cycles. EEVEE Next uses whatever GPU context Blender
    was launched with, so for EEVEE the decisive factor is launching with a
    real GPU context (EGL) rather than a software display like xvfb.

    Every step is guarded: if anything about the preferences API differs on
    this build, the function reports it and returns instead of raising, so a
    render never dies because of device configuration.

    Args:
        prefer: 'OPTIX', 'CUDA', 'HIP', 'ONEAPI', 'METAL' or None to auto-pick.
                Defaults to the IAVIDEO_GPU_BACKEND env var, else auto.

    Returns:
        dict with 'backend', 'devices' (list of enabled names), 'ok' (bool)
    """
    result = {'backend': None, 'devices': [], 'ok': False, 'note': ''}

    try:
        prefs = bpy.context.preferences
        cprefs = prefs.addons['cycles'].preferences
    except Exception as e:
        result['note'] = f"Cycles preferences unavailable: {e}"
        print(f"⚠ GPU setup skipped — {result['note']}")
        return result

    prefer = prefer or os.environ.get('IAVIDEO_GPU_BACKEND') or None

    # OPTIX first: on an RTX card it is normally faster than CUDA
    candidates = [prefer] if prefer else ['OPTIX', 'CUDA', 'HIP', 'ONEAPI', 'METAL']

    chosen = None
    for backend in candidates:
        if not backend:
            continue
        try:
            cprefs.compute_device_type = backend
        except (TypeError, AttributeError):
            continue  # not supported on this build

        try:
            devices = cprefs.get_devices_for_type(backend)
        except (AttributeError, TypeError):
            try:
                cprefs.get_devices()
                devices = [d for d in cprefs.devices if d.type == backend]
            except Exception:
                devices = []

        if devices:
            chosen = backend
            break

    if not chosen:
        result['note'] = "No GPU compute devices found; rendering on CPU"
        print(f"⚠ {result['note']}")
        return result

    result['backend'] = chosen

    # Enable every GPU of the chosen type; leave CPU off so it does not
    # bottleneck the tiles on a fast card.
    try:
        for device in cprefs.devices:
            if device.type == chosen:
                device.use = True
                result['devices'].append(device.name)
            elif device.type == 'CPU':
                device.use = False
    except Exception as e:
        result['note'] = f"Could not toggle devices: {e}"
        print(f"⚠ {result['note']}")
        return result

    # Point the scene at GPU compute (no-op for EEVEE, required for Cycles)
    try:
        bpy.context.scene.cycles.device = 'GPU'
    except (AttributeError, TypeError):
        pass

    result['ok'] = bool(result['devices'])

    print(f"✓ GPU backend: {chosen}")
    for name in result['devices']:
        print(f"    · {name}")
    if not result['devices']:
        print("    (backend selected but no devices enabled — will use CPU)")

    return result


def report_render_device():
    """Print what the current scene will actually render on."""
    scene = bpy.context.scene
    engine = getattr(scene.render, 'engine', '?')
    print(f"\n{'='*50}")
    print(f"Render engine: {engine}")

    if 'CYCLES' in str(engine):
        dev = getattr(getattr(scene, 'cycles', None), 'device', '?')
        print(f"Cycles device: {dev}")
        if dev != 'GPU':
            print("⚠ Cycles is set to CPU — GPU will NOT be used")
    else:
        # EEVEE: the GPU context comes from how Blender was launched
        print("EEVEE renders on the GPU context Blender was launched with.")
        print("If launched under xvfb (software GL), this is CPU-bound.")
        try:
            import gpu
            renderer = gpu.platform.renderer_get()
            vendor = gpu.platform.vendor_get()
            print(f"GPU renderer: {renderer}")
            print(f"GPU vendor:   {vendor}")
            soft = any(s in str(renderer).lower()
                       for s in ('llvmpipe', 'softpipe', 'swrast', 'software'))
            if soft:
                print("⚠ SOFTWARE rasterizer detected — EEVEE is running on CPU.")
                print("  Launch Blender with an EGL/GPU context instead of xvfb.")
            else:
                print("✓ Hardware GPU context detected.")
        except Exception as e:
            print(f"(could not query GPU context: {e})")
    print(f"{'='*50}\n")


def render_to_image_sequence(
    output_dir: str,
    start_frame: int = 1,
    end_frame: int = None,
    format_type: str = 'PNG',
    resume: bool = True
) -> bool:
    """
    Render animation as image sequence (more reliable for long renders).

    Renders frame by frame rather than via a single animation call, so an
    interrupted run can resume: at ~3400 frames a pod dying at frame 3000
    would otherwise mean restarting from zero.

    Args:
        output_dir: Directory for image sequence
        start_frame: Starting frame
        end_frame: Ending frame
        format_type: Image format ('PNG', 'JPEG', 'OPEN_EXR')
        resume: Skip frames already present on disk (set IAVIDEO_NO_RESUME=1
                to force a full re-render)
    
    Returns:
        bool: Success status
    """
    scene = bpy.context.scene
    
    # Configure for image sequence
    scene.render.image_settings.file_format = format_type
    
    if format_type == 'PNG':
        # RGB (not RGBA): the scene has an opaque floor, so the alpha channel
        # is wasted bytes. Higher compression trades a little CPU for a large
        # disk saving — critical at ~3400 frames per video.
        scene.render.image_settings.color_mode = 'RGB'
        scene.render.image_settings.compression = 50
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
    end_frame = int(scene.frame_end)

    os.makedirs(output_dir, exist_ok=True)

    if os.environ.get('IAVIDEO_NO_RESUME', '').lower() in ('1', 'true', 'yes'):
        resume = False

    total = end_frame - start_frame + 1
    if resume:
        todo = pending_frames(output_dir, start_frame, end_frame, format_type)
        already = total - len(todo)
        if already:
            print(f"↻ Resume: {already}/{total} frames already on disk, "
                  f"{len(todo)} remaining")
    else:
        todo = list(range(start_frame, end_frame + 1))

    print(f"\n{'='*50}")
    print(f"Rendering image sequence: {format_type}")
    print(f"Frames: {start_frame}-{end_frame} ({len(todo)} to render)")
    print(f"Output: {output_dir}/frame_XXXX.{format_type.lower()}")
    print(f"{'='*50}\n")

    if not todo:
        print("✓ All frames already rendered; nothing to do.")
        return True

    import time as _time
    started = _time.time()

    try:
        for i, frame in enumerate(todo, 1):
            scene.frame_set(frame)
            # Explicit per-frame path so resume can detect exactly what exists
            scene.render.filepath = _frame_path(output_dir, frame, format_type)
            bpy.ops.render.render(write_still=True)

            if i == 1 or i % 25 == 0 or i == len(todo):
                elapsed = _time.time() - started
                rate = i / elapsed if elapsed > 0 else 0
                remaining = (len(todo) - i) / rate if rate > 0 else 0
                print(f"  frame {frame} — {i}/{len(todo)} "
                      f"({rate:.2f} fps, ~{remaining/60:.1f} min left)")

        print(f"\n✓ Image sequence render complete!")
        return True
    except KeyboardInterrupt:
        print(f"\n⚠ Interrupted. Progress is saved — re-run to resume.")
        return False
    except Exception as e:
        print(f"\n⚠ Render failed at frame {frame}: {e}")
        print(f"  Completed frames are kept; re-run to resume from here.")
        return False


def prepend_inverted_hook(video_path: str, output_path: str,
                          teaser_seconds: float = 1.5,
                          black_seconds: float = 0.12,
                          crf: int = 18, fps: int = None) -> bool:
    """
    Prepend an inverted hook: a teaser of the payoff, then a hard cut to black,
    then the full run from the smallest object.

    The sweep is ordered smallest-to-largest, so the opening seconds — where
    the viewer decides whether to stay — show the least impressive object and
    the payoff lands near the end, after most of the audience has left.
    Showing the payoff first poses a question instead of a staircase.

    Implemented with a single filter_complex pass (trim + concat) rather than
    intermediate files, so this costs one encode, not three.

    Args:
        video_path: Rendered video (smallest to largest)
        output_path: Destination with the hook prepended
        teaser_seconds: Length of the payoff teaser taken from the end
        black_seconds: Hard-cut black gap between teaser and main body
        crf: Quality for the single re-encode
        fps: Frame rate (must match the source)
    """
    import subprocess

    fps = DEFAULT_FPS if fps is None else fps

    try:
        probe = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)],
            capture_output=True, text=True
        )
        duration = float(probe.stdout.strip())
    except (ValueError, AttributeError):
        print("⚠ Could not read video duration; skipping inverted hook")
        return False

    if duration <= teaser_seconds + 1.0:
        print(f"⚠ Video too short ({duration:.1f}s) for an inverted hook; skipping")
        return False

    teaser_start = max(0.0, duration - teaser_seconds)

    # Resolution must match across concat inputs, so read it from the source
    try:
        res_probe = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'stream=width,height', '-of', 'csv=p=0:s=x',
             str(video_path)],
            capture_output=True, text=True
        )
        w, h = res_probe.stdout.strip().split('x')
    except Exception:
        w, h = '1920', '1080'

    filter_complex = (
        f"[0:v]trim=start={teaser_start:.3f}:end={duration:.3f},"
        f"setpts=PTS-STARTPTS[teaser];"
        f"color=c=black:s={w}x{h}:d={black_seconds}:r={fps}[blk];"
        f"[0:v]trim=start=0,setpts=PTS-STARTPTS[main];"
        f"[teaser][blk][main]concat=n=3:v=1[out]"
    )

    cmd = [
        'ffmpeg', '-y',
        '-i', str(video_path),
        '-filter_complex', filter_complex,
        '-map', '[out]',
        '-c:v', 'libx264',
        '-preset', os.environ.get('IAVIDEO_X264_PRESET', 'medium'),
        '-crf', str(crf),
        '-pix_fmt', 'yuv420p',
        '-colorspace', 'bt709',
        '-color_primaries', 'bt709',
        '-color_trc', 'bt709',
        '-movflags', '+faststart',
        str(output_path)
    ]

    print(f"\nPrepending inverted hook ({teaser_seconds}s teaser from {teaser_start:.1f}s)...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✓ Inverted hook applied: {output_path}")
        return True

    print(f"⚠ Inverted hook failed: {result.stderr[-600:]}")
    return False


def convert_sequence_to_video(
    sequence_dir: str,
    output_path: str,
    fps: int = None,
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
    fps = DEFAULT_FPS if fps is None else fps
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
        # NOTE: no audio flags here on purpose. Audio is muxed in a later
        # phase with -c:v copy, avoiding a second video encode.
        use_nvenc = os.environ.get('IAVIDEO_USE_NVENC', '').lower() in ('1', 'true', 'yes')

        cmd = [
            'ffmpeg', '-y',  # Overwrite output
            '-framerate', str(fps),
            '-i', os.path.join(sequence_dir, frame_pattern),
        ]

        if use_nvenc:
            # GPU encoding (RunPod): dramatically faster than libx264 at scale
            cmd += [
                '-c:v', 'h264_nvenc',
                '-preset', 'p5',
                '-rc', 'vbr',
                '-cq', str(crf),
                '-b:v', '0',
            ]
        else:
            cmd += [
                '-c:v', 'libx264',
                '-crf', str(crf),
                '-preset', os.environ.get('IAVIDEO_X264_PRESET', 'medium'),
            ]

        cmd += [
            '-pix_fmt', 'yuv420p',
            # Declare colour space so YouTube does not re-interpret it
            '-colorspace', 'bt709',
            '-color_primaries', 'bt709',
            '-color_trc', 'bt709',
            # Move the moov atom to the front for progressive streaming
            '-movflags', '+faststart',
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
    setup_color_management()
    setup_cinematic_compositor()

    # Enable GPU compute (Cycles) and report what will actually be used.
    # Both are non-fatal: a failure here degrades to CPU, it never aborts.
    try:
        setup_gpu_devices()
    except Exception as e:
        print(f"⚠ GPU setup raised ({e}); continuing on CPU")
    try:
        report_render_device()
    except Exception:
        pass
    
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
                fps=DEFAULT_FPS,
                resolution=(res_x, res_y),
                crf=18
            )
            
            # Cleanup sequence if successful
            if success:
                print(f"\n✓ Final video: {output_video}")

                # Remove the PNG sequence: at ~3400 frames this is several GB
                # per video and will fill the disk within a few runs.
                # Set IAVIDEO_KEEP_FRAMES=1 to retain frames for debugging.
                if os.environ.get('IAVIDEO_KEEP_FRAMES', '').lower() in ('1', 'true', 'yes'):
                    print(f"  ℹ Keeping frame sequence (IAVIDEO_KEEP_FRAMES set): {sequence_dir}")
                else:
                    try:
                        freed = sum(
                            os.path.getsize(os.path.join(sequence_dir, f))
                            for f in os.listdir(sequence_dir)
                            if os.path.isfile(os.path.join(sequence_dir, f))
                        )
                        shutil.rmtree(sequence_dir)
                        print(f"  ✓ Removed temp sequence, freed {freed / (1024**3):.2f} GB")
                    except Exception as e:
                        print(f"  ⚠ Could not clean temp sequence: {e}")
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
    
    # When launched via Blender (blender -b -P render_pipeline.py -- --output ...),
    # sys.argv includes Blender's own flags before the "--" separator.
    # Only parse the arguments that come after "--".
    if "--" in sys.argv:
        cli_args = sys.argv[sys.argv.index("--") + 1:]
    else:
        cli_args = sys.argv[1:]

    args = parser.parse_args(cli_args)
    
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
