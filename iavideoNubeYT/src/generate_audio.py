"""
generate_audio.py - FoleyCrafter / MMAudio & FFmpeg audio multiplexing

Generates cinematic audio for scale comparison videos:
- Low-frequency whooshes for camera transitions
- Mechanical clicks for scale markers
- Atmospheric droning for background ambiance
- FFmpeg-based audio multiplexing with rendered video
"""

import os
import sys
import subprocess
import numpy as np
from pathlib import Path
from typing import Optional, List, Tuple


def check_ffmpeg() -> bool:
    """Check if FFmpeg is available in system PATH."""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ FFmpeg detected: {result.stdout.split()[2]}")
            return True
        else:
            print("⚠ FFmpeg not found or outdated")
            return False
    except FileNotFoundError:
        print("⚠ FFmpeg not installed. Install with: sudo apt-get install ffmpeg")
        return False


def generate_sine_wave(
    frequency: float,
    duration: float,
    sample_rate: int = 48000,
    amplitude: float = 0.5,
    fade_in: float = 0.1,
    fade_out: float = 0.3
) -> np.ndarray:
    """
    Generate a sine wave tone with fade envelopes.
    
    Args:
        frequency: Frequency in Hz
        duration: Duration in seconds
        sample_rate: Audio sample rate (default 48kHz)
        amplitude: Volume amplitude (0.0-1.0)
        fade_in: Fade-in duration in seconds
        fade_out: Fade-out duration in seconds
    
    Returns:
        numpy array of audio samples
    """
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    wave = amplitude * np.sin(2 * np.pi * frequency * t)
    
    # Apply fade-in
    fade_in_samples = int(fade_in * sample_rate)
    fade_in_curve = np.linspace(0, 1, fade_in_samples)
    wave[:fade_in_samples] *= fade_in_curve
    
    # Apply fade-out
    fade_out_samples = int(fade_out * sample_rate)
    fade_out_curve = np.linspace(1, 0, fade_out_samples)
    wave[-fade_out_samples:] *= fade_out_curve
    
    return wave


def generate_whoosh(
    duration: float = 2.0,
    sample_rate: int = 48000,
    direction: str = "up"
) -> np.ndarray:
    """
    Generate cinematic whoosh sound effect.
    
    Args:
        duration: Duration in seconds
        sample_rate: Audio sample rate
        direction: "up" for rising pitch, "down" for falling
    
    Returns:
        numpy array of audio samples
    """
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Frequency sweep (logarithmic for natural feel)
    if direction == "up":
        freq_start, freq_end = 80, 400  # Low to mid frequency
    else:
        freq_start, freq_end = 400, 80
    
    # Logarithmic frequency sweep
    freq = np.exp(np.log(freq_start) + (np.log(freq_end) - np.log(freq_start)) * (t / duration))
    
    # Generate swept sine wave
    phase = np.cumsum(freq) / sample_rate
    wave = 0.4 * np.sin(2 * np.pi * phase)
    
    # Add noise layer for texture
    noise = 0.1 * np.random.randn(len(wave))
    wave += noise
    
    # Apply envelope (smooth attack and release)
    envelope = np.ones_like(t)
    attack = int(0.2 * sample_rate)
    release = int(0.3 * sample_rate)
    
    envelope[:attack] = np.linspace(0, 1, attack)
    envelope[-release:] = np.linspace(1, 0, release)
    
    wave *= envelope
    
    # Low-pass filter simulation (simple moving average)
    kernel_size = 5
    wave = np.convolve(wave, np.ones(kernel_size)/kernel_size, mode='same')
    
    return wave


def generate_mechanical_click(
    duration: float = 0.3,
    sample_rate: int = 48000,
    pitch: str = "high"
) -> np.ndarray:
    """
    Generate mechanical click sound for UI/scale markers.
    
    Args:
        duration: Duration in seconds
        sample_rate: Audio sample rate
        pitch: "high" or "low" pitch variant
    
    Returns:
        numpy array of audio samples
    """
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Base frequency
    freq = 800 if pitch == "high" else 400
    
    # Short burst with quick decay
    wave = 0.6 * np.sin(2 * np.pi * freq * t)
    
    # Very fast attack and decay
    decay = int(0.05 * sample_rate)
    envelope = np.exp(-t * 30)  # Quick exponential decay
    wave *= envelope
    
    # Add transient click at start
    click_duration = int(0.01 * sample_rate)
    wave[:click_duration] *= np.random.uniform(0.8, 1.0, click_duration)
    
    return wave


def generate_atmospheric_drone(
    duration: float = 10.0,
    sample_rate: int = 48000,
    base_freq: float = 60.0,
    intensity: str = "medium"
) -> np.ndarray:
    """
    Generate atmospheric background drone.
    
    Args:
        duration: Duration in seconds
        sample_rate: Audio sample rate
        base_freq: Base frequency in Hz (lower = darker)
        intensity: "low", "medium", or "high"
    
    Returns:
        numpy array of audio samples
    """
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Intensity settings
    if intensity == "low":
        harmonics = [1, 2, 3]
        amplitudes = [0.3, 0.15, 0.05]
    elif intensity == "medium":
        harmonics = [1, 2, 3, 4, 5]
        amplitudes = [0.25, 0.15, 0.1, 0.07, 0.05]
    else:  # high
        harmonics = [1, 2, 3, 4, 5, 6, 7]
        amplitudes = [0.2, 0.15, 0.12, 0.1, 0.08, 0.06, 0.04]
    
    # Build harmonic stack
    wave = np.zeros_like(t)
    for harm, amp in zip(harmonics, amplitudes):
        freq = base_freq * harm
        # Slight detune for richness
        detune = freq * (1 + 0.01 * np.sin(t * 0.5))
        wave += amp * np.sin(2 * np.pi * detune * t)
    
    # Add subtle modulation
    modulation = 1 + 0.1 * np.sin(2 * np.pi * 0.2 * t)
    wave *= modulation
    
    # Gentle fade-in and fade-out
    fade_duration = int(1.0 * sample_rate)
    fade_in = np.linspace(0, 1, fade_duration)
    fade_out = np.linspace(1, 0, fade_duration)
    
    wave[:fade_duration] *= fade_in
    wave[-fade_duration:] *= fade_out
    
    # Normalize to prevent clipping
    max_amp = np.max(np.abs(wave))
    if max_amp > 0:
        wave *= 0.8 / max_amp
    
    return wave


def save_audio_file(
    audio_data: np.ndarray,
    output_path: str,
    sample_rate: int = 48000,
    normalize: bool = True
):
    """
    Save audio data to WAV file using FFmpeg pipe.
    
    Args:
        audio_data: Numpy array of audio samples
        output_path: Path for output WAV file
        sample_rate: Sample rate in Hz
        normalize: Normalize audio levels
    """
    # Normalize if requested
    if normalize:
        max_amp = np.max(np.abs(audio_data))
        if max_amp > 0:
            audio_data = audio_data / max_amp * 0.9
    
    # Convert to 16-bit PCM
    audio_int16 = (audio_data * 32767).astype(np.int16)
    
    # Create output directory
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Write WAV file directly
    import wave
    
    with wave.open(output_path, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_int16.tobytes())
    
    print(f"  ✓ Saved: {output_path}")


def generate_transition_whooshes(
    timestamps: List[float],
    total_duration: float,
    output_dir: str,
    sample_rate: int = 48000
) -> List[str]:
    """
    Generate whoosh sounds for camera transitions.
    
    Args:
        timestamps: List of transition times in seconds
        total_duration: Total video duration
        output_dir: Directory for audio files
        sample_rate: Audio sample rate
    
    Returns:
        List of generated file paths
    """
    print(f"\nGenerating {len(timestamps)} transition whooshes...")
    
    generated_files = []
    
    for i, ts in enumerate(timestamps):
        # Determine direction based on position
        direction = "up" if i % 2 == 0 else "down"
        
        # Generate whoosh
        whoosh = generate_whoosh(duration=2.0, sample_rate=sample_rate, direction=direction)
        
        # Save with timestamp name
        output_path = os.path.join(output_dir, f"whoosh_{i:03d}_{ts:.1f}s.wav")
        save_audio_file(whoosh, output_path, sample_rate)
        generated_files.append((output_path, ts))
    
    return generated_files


def generate_marker_clicks(
    timestamps: List[float],
    output_dir: str,
    sample_rate: int = 48000
) -> List[str]:
    """
    Generate mechanical clicks for scale marker appearances.
    
    Args:
        timestamps: List of marker appearance times
        output_dir: Directory for audio files
        sample_rate: Audio sample rate
    
    Returns:
        List of generated file paths
    """
    print(f"\nGenerating {len(timestamps)} marker clicks...")
    
    generated_files = []
    
    for i, ts in enumerate(timestamps):
        # Alternate between high and low pitch
        pitch = "high" if i % 2 == 0 else "low"
        
        # Generate click
        click = generate_mechanical_click(duration=0.3, sample_rate=sample_rate, pitch=pitch)
        
        # Save
        output_path = os.path.join(output_dir, f"click_{i:03d}_{ts:.1f}s.wav")
        save_audio_file(click, output_path, sample_rate)
        generated_files.append((output_path, ts))
    
    return generated_files


def generate_background_drone(
    duration: float,
    output_dir: str,
    sample_rate: int = 48000,
    intensity: str = "medium"
) -> str:
    """
    Generate continuous atmospheric drone.
    
    Args:
        duration: Duration in seconds
        output_dir: Directory for audio file
        sample_rate: Audio sample rate
        intensity: Drone intensity level
    
    Returns:
        Path to generated file
    """
    print(f"\nGenerating background drone ({duration:.1f}s)...")
    
    drone = generate_atmospheric_drone(
        duration=duration,
        sample_rate=sample_rate,
        base_freq=50.0,  # Deep cinematic drone
        intensity=intensity
    )
    
    output_path = os.path.join(output_dir, "atmosphere_drone.wav")
    save_audio_file(drone, output_path, sample_rate)
    
    return output_path


def mix_audio_with_video(
    video_path: str,
    audio_files: List[Tuple[str, float]],
    background_track: str,
    output_path: str,
    video_fps: int = 60
):
    """
    Mix all audio elements with video using FFmpeg.
    
    Args:
        video_path: Path to rendered video (without audio)
        audio_files: List of (file_path, timestamp_seconds) tuples
        background_track: Path to background drone/ambience
        output_path: Final output video path
        video_fps: Video frame rate
    """
    print(f"\nMixing audio with video...")
    print(f"  Video: {video_path}")
    print(f"  Audio elements: {len(audio_files)}")
    print(f"  Background: {background_track}")
    print(f"  Output: {output_path}")
    
    # Create FFmpeg filter complex for mixing
    inputs = ['-i', video_path]
    
    # Add all SFX files with delay filters
    sfx_inputs = []
    for i, (audio_file, timestamp) in enumerate(audio_files):
        if os.path.exists(audio_file):
            delay_ms = int(timestamp * 1000)
            sfx_inputs.extend([
                '-i', audio_file,
                '-af', f'adelay={delay_ms}|{delay_ms}'
            ])
    
    # Add background track
    inputs.extend(['-i', background_track])
    
    # Build filter complex
    # This mixes all audio tracks together
    num_inputs = len(sfx_inputs) // 2 + 2  # SFX pairs + video + background
    
    filter_parts = []
    
    # Label all inputs
    for i in range(num_inputs):
        filter_parts.append(f'[{i}:a]')
    
    # Mix all together
    filter_complex = ''.join(filter_parts) + f'amix=inputs={num_inputs}:duration=longest[audio_out]'
    
    # FFmpeg command
    cmd = [
        'ffmpeg', '-y',
        *inputs,
        '-filter_complex', filter_complex,
        '-map', '0:v',  # Video from first input
        '-map', '[audio_out]',
        '-c:v', 'copy',  # Copy video codec (no re-encode)
        '-c:a', 'aac',
        '-b:a', '192k',
        '-movflags', '+faststart',  # Progressive streaming for YouTube
        '-shortest',
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"\n✓ Audio mixed successfully!")
            print(f"  Final video: {output_path}")
            return True
        else:
            print(f"\n⚠ FFmpeg error: {result.stderr}")
            
            # Try simpler approach: just add background music
            # NOTE: the rendered video has no audio stream, so we must NOT
            # reference [0:a] here — map the background track directly.
            print("\nTrying simplified audio mix...")
            simple_cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-stream_loop', '-1', '-i', background_track,
                '-map', '0:v',
                '-map', '1:a',
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-movflags', '+faststart',
                '-shortest',
                output_path
            ]
            
            result2 = subprocess.run(simple_cmd, capture_output=True, text=True)
            if result2.returncode == 0:
                print(f"✓ Simplified mix successful")
                return True
            else:
                print(f"⚠ Simplified mix also failed")
                return False
                
    except Exception as e:
        print(f"⚠ Audio mixing error: {e}")
        return False


def create_complete_audio_track(
    video_duration: float,
    transition_times: List[float],
    marker_times: List[float],
    output_dir: str = "./assets/audio",
    sample_rate: int = 48000
) -> dict:
    """
    Generate complete audio package for a video.
    
    Args:
        video_duration: Total video duration in seconds
        transition_times: Timestamps for camera transitions
        marker_times: Timestamps for scale marker appearances
        output_dir: Directory for audio files
        sample_rate: Audio sample rate
    
    Returns:
        dict: Paths to generated audio files
    """
    print("\n" + "="*50)
    print("GENERATING CINEMATIC AUDIO TRACK")
    print("="*50)
    
    os.makedirs(output_dir, exist_ok=True)
    
    results = {}
    
    # Generate background drone
    drone_path = generate_background_drone(
        duration=video_duration,
        output_dir=output_dir,
        sample_rate=sample_rate,
        intensity="medium"
    )
    results['drone'] = drone_path
    
    # Generate transition whooshes
    whooshes = generate_transition_whooshes(
        timestamps=transition_times,
        total_duration=video_duration,
        output_dir=output_dir,
        sample_rate=sample_rate
    )
    results['whooshes'] = whooshes
    
    # Generate marker clicks
    clicks = generate_marker_clicks(
        timestamps=marker_times,
        output_dir=output_dir,
        sample_rate=sample_rate
    )
    results['clicks'] = clicks
    
    print(f"\n{'='*50}")
    print(f"✓ Audio generation complete")
    print(f"  Background: {drone_path}")
    print(f"  Whooshes: {len(whooshes)}")
    print(f"  Clicks: {len(clicks)}")
    print(f"{'='*50}\n")
    
    return results


# Entry point
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate cinematic audio for scale comparison videos")
    parser.add_argument("--duration", type=float, default=30.0,
                       help="Video duration in seconds")
    parser.add_argument("--transitions", type=str, default="5,10,15,20,25",
                       help="Comma-separated transition timestamps")
    parser.add_argument("--markers", type=str, default="0,5,10,15,20",
                       help="Comma-separated marker timestamps")
    parser.add_argument("--output", type=str, default="./assets/audio",
                       help="Output directory for audio files")
    parser.add_argument("--mix-with-video", type=str,
                       help="Path to video file for audio mixing")
    parser.add_argument("--output-video", type=str,
                       help="Path for final video with audio")
    
    args = parser.parse_args()
    
    # Check prerequisites
    if not check_ffmpeg():
        print("\n⚠ WARNING: FFmpeg not available")
        print("Audio generation will work, but mixing with video requires FFmpeg")
    
    # Parse timestamps
    transitions = [float(x.strip()) for x in args.transitions.split(',')]
    markers = [float(x.strip()) for x in args.markers.split(',')]
    
    # Generate audio
    audio_result = create_complete_audio_track(
        video_duration=args.duration,
        transition_times=transitions,
        marker_times=markers,
        output_dir=args.output
    )
    
    # Mix with video if requested
    if args.mix_with_video and args.output_video:
        if not os.path.exists(args.mix_with_video):
            print(f"⚠ Video file not found: {args.mix_with_video}")
        else:
            # Collect all audio files with timestamps
            all_audio = []
            all_audio.extend(audio_result.get('whooshes', []))
            all_audio.extend(audio_result.get('clicks', []))
            
            mix_audio_with_video(
                video_path=args.mix_with_video,
                audio_files=all_audio,
                background_track=audio_result['drone'],
                output_path=args.output_video
            )
