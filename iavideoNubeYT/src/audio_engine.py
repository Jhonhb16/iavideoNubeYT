"""
audio_engine.py - Multi-layer cinematic sound design with precise synchronization

Features:
- Read vehicle timestamps from Blender-generated data/timestamps.json
- Generate synthetic SFX (whooshes, sub-bass rumble, metallic impacts)
- Procedural stereo ambient music track
- FFmpeg mixing with YouTube loudness normalization (-14 LUFS, -1 dBTP peak)
"""

import os
import sys
import json
import csv
import math
import struct
import wave
from pathlib import Path
from typing import List, Dict, Optional


class AudioEngine:
    """Multi-layer cinematic audio generator for scale comparison videos."""
    
    def __init__(self, output_dir="assets/audio", sample_rate=48000):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.sample_rate = sample_rate
        
        # Audio constants
        self.duration_per_vehicle = 5.0  # seconds
        self.transition_duration = 1.8   # seconds for camera pause/focus
        
    def generate_sine_wave(self, frequency: float, duration: float, 
                           amplitude: float = 0.5, fade_in: float = 0.01, 
                           fade_out: float = 0.01) -> bytes:
        """Generate a sine wave with optional fade in/out."""
        num_samples = int(self.sample_rate * duration)
        samples = []
        
        for i in range(num_samples):
            t = i / self.sample_rate
            
            # Apply fade in/out
            envelope = 1.0
            if t < fade_in:
                envelope = t / fade_in
            elif t > duration - fade_out:
                envelope = (duration - t) / fade_out
            
            # Generate sample
            sample = amplitude * envelope * math.sin(2 * math.pi * frequency * t)
            samples.append(sample)
        
        # Convert to 16-bit PCM
        return struct.pack(f'{len(samples)}h', *[int(s * 32767) for s in samples])
    
    def generate_white_noise(self, duration: float, amplitude: float = 0.3) -> bytes:
        """Generate white noise for impact effects."""
        import random
        num_samples = int(self.sample_rate * duration)
        samples = [amplitude * (random.random() * 2 - 1) for _ in range(num_samples)]
        return struct.pack(f'{num_samples}h', *[int(s * 32767) for s in samples])
    
    def generate_cinematic_whoosh(self, duration: float = 2.0, 
                                   start_freq: float = 100, 
                                   end_freq: float = 800) -> bytes:
        """Generate cinematic whoosh effect with frequency sweep."""
        num_samples = int(self.sample_rate * duration)
        samples = []
        
        for i in range(num_samples):
            t = i / self.sample_rate
            progress = t / duration
            
            # Frequency sweep (exponential)
            freq = start_freq * (end_freq / start_freq) ** progress
            
            # Amplitude envelope (swell then decay)
            envelope = math.sin(math.pi * progress) ** 2
            
            # Multiple harmonics for richness
            sample = 0
            for harmonic in [1, 2, 4]:
                sample += (1/harmonic) * math.sin(2 * math.pi * freq * harmonic * t)
            
            sample *= amplitude * envelope * 0.3
            samples.append(sample)
        
        return struct.pack(f'{len(samples)}h', *[int(s * 32767) for s in samples])
    
    def generate_sub_bass_rumble(self, duration: float = 3.0, 
                                  frequency: float = 40,
                                  modulation_freq: float = 0.5) -> bytes:
        """Generate deep sub-bass rumble for large objects (>20m)."""
        num_samples = int(self.sample_rate * duration)
        samples = []
        
        for i in range(num_samples):
            t = i / self.sample_rate
            
            # Low frequency oscillator for rumble modulation
            mod = 1 + 0.3 * math.sin(2 * math.pi * modulation_freq * t)
            
            # Sub-bass fundamental
            sample = math.sin(2 * math.pi * frequency * t)
            
            # Add harmonics
            sample += 0.5 * math.sin(2 * math.pi * frequency * 2 * t)
            sample += 0.25 * math.sin(2 * math.pi * frequency * 3 * t)
            
            # Amplitude envelope (slow attack, long release)
            attack = min(1.0, t / 0.5)
            release = max(0, 1 - (t - (duration - 1.0)) / 1.0) if t > duration - 1.0 else 1.0
            envelope = attack * release
            
            sample *= mod * envelope * 0.4
            samples.append(sample)
        
        return struct.pack(f'{len(samples)}h', *[int(s * 32767) for s in samples])
    
    def generate_metallic_impact(self, duration: float = 0.5, 
                                  frequency: float = 800) -> bytes:
        """Generate metallic click/impact for armored vehicles."""
        num_samples = int(self.sample_rate * duration)
        samples = []
        
        for i in range(num_samples):
            t = i / self.sample_rate
            
            # Metallic resonance (high frequency with decay)
            decay = math.exp(-t * 15)
            sample = math.sin(2 * math.pi * frequency * t) * decay
            
            # Add inharmonic partials for metallic character
            sample += 0.3 * math.sin(2 * math.pi * frequency * 1.41 * t) * decay
            sample += 0.2 * math.sin(2 * math.pi * frequency * 1.73 * t) * decay
            
            sample *= decay * 0.5
            samples.append(sample)
        
        return struct.pack(f'{len(samples)}h', *[int(s * 32767) for s in samples])
    
    def generate_ambient_drone(self, duration: float = 60.0, 
                                base_frequency: float = 55) -> bytes:
        """Generate continuous atmospheric drone background."""
        num_samples = int(self.sample_rate * duration)
        samples = []
        
        # Drone frequencies (pentatonic scale for cinematic feel)
        frequencies = [
            base_frequency,           # A1
            base_frequency * 1.125,   # B1
            base_frequency * 1.25,    # C#2
            base_frequency * 1.5,     # E2
            base_frequency * 1.667,   # F#2
            base_frequency * 2,       # A2 (octave)
        ]
        
        # LFO for slow modulation
        lfo_freq = 0.1
        
        for i in range(num_samples):
            t = i / self.sample_rate
            
            # Slow amplitude modulation
            lfo = 0.7 + 0.3 * math.sin(2 * math.pi * lfo_freq * t)
            
            # Sum multiple detuned oscillators
            sample = 0
            for j, freq in enumerate(frequencies):
                # Slight detuning for each voice
                detune = 1 + (j % 2) * 0.01
                phase_shift = j * math.pi / 4
                
                sample += math.sin(2 * math.pi * freq * detune * t + phase_shift)
            
            # Normalize and apply LFO
            sample /= len(frequencies)
            sample *= lfo * 0.15
            
            samples.append(sample)
        
        return struct.pack(f'{len(samples)}h', *[int(s * 32767) for s in samples])
    
    def generate_stereo_ambient_music(self, duration: float = 60.0) -> tuple:
        """Generate procedural stereo ambient music track."""
        print(f"  Generating {duration:.1f}s stereo ambient track...")
        
        # Base drone in left channel
        left_samples = self.generate_ambient_drone(duration, base_frequency=55)
        
        # Slightly different drone in right channel for stereo width
        right_samples = self.generate_ambient_drone(duration, base_frequency=55 * 1.01)
        
        return left_samples, right_samples
    
    def save_wav_file(self, filename: str, audio_data: bytes, 
                      channels: int = 1, sample_rate: int = None):
        """Save audio data as WAV file."""
        if sample_rate is None:
            sample_rate = self.sample_rate
        
        filepath = self.output_dir / filename
        
        with wave.open(str(filepath), 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)
        
        print(f"  ✓ Saved: {filepath}")
        return filepath
    
    def create_transition_whoosh(self, timestamp: float, duration: float = 2.0) -> Dict:
        """Create whoosh transition effect at specific timestamp."""
        return {
            'type': 'whoosh',
            'timestamp': timestamp,
            'duration': duration,
            'data': self.generate_cinematic_whoosh(duration)
        }
    
    def create_vehicle_sfx(self, vehicle_data: Dict, timestamp: float) -> List[Dict]:
        """Generate appropriate SFX based on vehicle characteristics."""
        sfx_list = []
        scale_m = float(vehicle_data.get('scale_m', 1.0))
        name = vehicle_data.get('name', '').lower()
        
        # Sub-bass rumble for large objects (>20m)
        if scale_m > 20:
            rumble_duration = min(4.0, scale_m / 100)
            sfx_list.append({
                'type': 'sub_bass',
                'timestamp': timestamp,
                'duration': rumble_duration,
                'data': self.generate_sub_bass_rumble(rumble_duration, frequency=30)
            })
        
        # Metallic impact for armored vehicles
        if any(term in name for term in ['tank', 'armor', 'panzer', 'abrams', 'sherman', 't90']):
            sfx_list.append({
                'type': 'metallic',
                'timestamp': timestamp,
                'duration': 0.5,
                'data': self.generate_metallic_impact(0.5, frequency=600)
            })
        
        # Whoosh for aircraft
        if any(term in name for term in ['apache', 'b2', 'an225', 'ac130', 'drone']):
            sfx_list.append({
                'type': 'whoosh',
                'timestamp': timestamp,
                'duration': 1.5,
                'data': self.generate_cinematic_whoosh(1.5, 200, 1200)
            })
        
        return sfx_list
    
    def load_timestamps(self, timestamps_path: str) -> Dict:
        """Load vehicle timestamps from JSON file."""
        try:
            with open(timestamps_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠ Timestamps file not found: {timestamps_path}")
            return {}
        except json.JSONDecodeError as e:
            print(f"⚠ Error parsing timestamps: {e}")
            return {}
    
    def load_vehicles(self, csv_path: str) -> List[Dict]:
        """Load vehicle data from CSV."""
        vehicles = []
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                vehicles.append(row)
        return vehicles
    
    def mix_audio_layers(self, video_duration: float, vehicles: List[Dict], 
                         timestamps: Dict) -> bytes:
        """Mix all audio layers together."""
        print(f"\nMixing audio layers for {video_duration:.1f}s video...")
        
        total_samples = int(self.sample_rate * video_duration)
        mixed_samples = [0.0] * total_samples
        
        # 1. Add ambient drone bed (entire duration)
        print("  Adding ambient drone bed...")
        ambient_data = self.generate_ambient_drone(video_duration, base_frequency=55)
        ambient_samples = struct.unpack(f'{len(ambient_data)//2}h', ambient_data)
        
        for i in range(min(len(ambient_samples), total_samples)):
            mixed_samples[i] += ambient_samples[i] / 32767 * 0.2
        
        # 2. Add transitions between vehicles
        print("  Adding transition whooshes...")
        num_vehicles = len(vehicles)
        for i in range(num_vehicles - 1):
            transition_time = (i + 1) * self.duration_per_vehicle
            if transition_time < video_duration:
                whoosh_data = self.generate_cinematic_whoosh(
                    self.transition_duration, 
                    start_freq=80, 
                    end_freq=600
                )
                whoosh_samples = struct.unpack(f'{len(whoosh_data)//2}h', whoosh_data)
                
                start_idx = int(transition_time * self.sample_rate)
                for j in range(min(len(whoosh_samples), total_samples - start_idx)):
                    mixed_samples[start_idx + j] += whoosh_samples[j] / 32767 * 0.3
        
        # 3. Add vehicle-specific SFX
        print("  Adding vehicle-specific SFX...")
        for i, vehicle in enumerate(vehicles):
            vehicle_time = i * self.duration_per_vehicle
            if vehicle_time >= video_duration:
                break
            
            sfx_list = self.create_vehicle_sfx(vehicle, vehicle_time)
            for sfx in sfx_list:
                sfx_samples = struct.unpack(f'{len(sfx["data"])//2}h', sfx['data'])
                start_idx = int(sfx['timestamp'] * self.sample_rate)
                
                for j in range(min(len(sfx_samples), total_samples - start_idx)):
                    mixed_samples[start_idx + j] += sfx_samples[j] / 32767 * 0.4
        
        # 4. Normalize to prevent clipping
        print("  Normalizing audio...")
        max_sample = max(abs(s) for s in mixed_samples) if mixed_samples else 0
        if max_sample > 0:
            # Normalize to -1 dBTP (approximately 0.89)
            target_peak = 0.89
            scale = target_peak / max_sample
            
            for i in range(len(mixed_samples)):
                mixed_samples[i] *= scale
        
        # Convert back to 16-bit PCM
        return struct.pack(f'{len(mixed_samples)}h', 
                          [max(-32768, min(32767, int(s * 32767))) for s in mixed_samples])
    
    def normalize_for_youtube(self, input_wav: Path, output_wav: Path):
        """Normalize audio to YouTube standards using FFmpeg (-14 LUFS, -1 dBTP)."""
        import subprocess
        
        try:
            # Check if FFmpeg is available
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            
            cmd = [
                'ffmpeg', '-y',
                '-i', str(input_wav),
                '-af', 'loudnorm=I=-14:TP=-1:LRA=11',
                '-ar', '48000',
                '-ac', '2',
                str(output_wav)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✓ Audio normalized for YouTube: {output_wav}")
                return True
            else:
                print(f"⚠ FFmpeg error: {result.stderr}")
                return False
                
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"⚠ FFmpeg not available for normalization: {e}")
            return False
    
    def generate_complete_audio(self, csv_path: str, timestamps_path: str, 
                                 video_duration: Optional[float] = None) -> Path:
        """Generate complete audio track for the video."""
        print("\n" + "="*50)
        print("Audio Engine - Cinematic Sound Design")
        print("="*50)
        
        # Load data
        vehicles = self.load_vehicles(csv_path)
        timestamps = self.load_timestamps(timestamps_path)
        
        if not vehicles:
            print("⚠ No vehicles found in CSV")
            return None
        
        # Calculate video duration if not provided
        if video_duration is None:
            video_duration = len(vehicles) * self.duration_per_vehicle + 5
        
        print(f"Vehicles: {len(vehicles)}")
        print(f"Video duration: {video_duration:.1f}s")
        
        # Mix all layers
        mixed_audio = self.mix_audio_layers(video_duration, vehicles, timestamps)
        
        # Save raw mix
        raw_output = self.output_dir / "audio_mix_raw.wav"
        self.save_wav_file("audio_mix_raw.wav", mixed_audio, channels=1)
        
        # Create stereo version
        print("\nCreating stereo version...")
        left_channel, right_channel = self.generate_stereo_ambient_music(video_duration)
        
        # Combine left and right channels
        stereo_data = b''
        left_samples = struct.unpack(f'{len(left_channel)//2}h', left_channel)
        right_samples = struct.unpack(f'{len(right_channel)//2}h', right_channel)
        
        for i in range(max(len(left_samples), len(right_samples))):
            left = left_samples[i] if i < len(left_samples) else 0
            right = right_samples[i] if i < len(right_samples) else 0
            stereo_data += struct.pack('hh', left, right)
        
        stereo_output = self.output_dir / "audio_mix_stereo.wav"
        self.save_wav_file("audio_mix_stereo.wav", stereo_data, channels=2)
        
        # Normalize for YouTube
        print("\nNormalizing for YouTube (-14 LUFS, -1 dBTP)...")
        normalized_output = self.output_dir / "audio_final_normalized.wav"
        self.normalize_for_youtube(stereo_output, normalized_output)
        
        # Also generate individual SFX elements for flexibility
        print("\nGenerating individual SFX elements...")
        self.save_wav_file("sfx_whoosh.wav", self.generate_cinematic_whoosh(2.0))
        self.save_wav_file("sfx_sub_bass.wav", self.generate_sub_bass_rumble(3.0))
        self.save_wav_file("sfx_metallic.wav", self.generate_metallic_impact(0.5))
        self.save_wav_file("sfx_ambient_drone.wav", self.generate_ambient_drone(60.0))
        
        print(f"\n✓ Audio generation complete!")
        print(f"Output directory: {self.output_dir}")
        print("="*50 + "\n")
        
        return normalized_output
    
    def mux_audio_to_video(self, video_path: Path, audio_path: Path, 
                           output_path: Path):
        """Mux audio track to video using FFmpeg."""
        import subprocess
        
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            
            cmd = [
                'ffmpeg', '-y',
                '-i', str(video_path),
                '-i', str(audio_path),
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '320k',
                '-shortest',
                str(output_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✓ Audio muxed to video: {output_path}")
                return True
            else:
                print(f"⚠ FFmpeg error: {result.stderr}")
                return False
                
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"⚠ FFmpeg not available: {e}")
            return False


def main():
    """Main entry point for audio engine."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Cinematic audio engine for scale comparison videos')
    parser.add_argument('--csv', default='data/military_vehicles.csv',
                       help='Path to CSV file with vehicle data')
    parser.add_argument('--timestamps', default='data/timestamps.json',
                       help='Path to JSON file with frame timestamps')
    parser.add_argument('--duration', type=float, default=None,
                       help='Video duration in seconds (auto-calculated if not provided)')
    parser.add_argument('--output-dir', default='assets/audio',
                       help='Output directory for audio files')
    parser.add_argument('--video', default=None,
                       help='Video file to mux audio with')
    parser.add_argument('--output-video', default=None,
                       help='Output video path after muxing')
    
    args = parser.parse_args()
    
    # Get script directory for relative paths
    script_dir = Path(__file__).parent.parent
    csv_path = script_dir / args.csv if not os.path.isabs(args.csv) else Path(args.csv)
    timestamps_path = script_dir / args.timestamps if not os.path.isabs(args.timestamps) else Path(args.timestamps)
    
    # Initialize engine
    engine = AudioEngine(
        output_dir=args.output_dir if os.path.isabs(args.output_dir) else script_dir / args.output_dir
    )
    
    # Generate audio
    audio_output = engine.generate_complete_audio(
        str(csv_path), 
        str(timestamps_path), 
        args.duration
    )
    
    # Mux to video if requested
    if args.video and args.output_video and audio_output:
        video_path = Path(args.video) if os.path.isabs(args.video) else script_dir / args.video
        output_path = Path(args.output_video) if os.path.isabs(args.output_video) else script_dir / args.output_video
        engine.mux_audio_to_video(video_path, audio_output, output_path)


if __name__ == "__main__":
    main()
