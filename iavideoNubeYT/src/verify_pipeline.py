#!/usr/bin/env python3
"""
Pipeline Quality Assurance Script
Validates integrity of final video output, thumbnail, audio streams, and timestamps.
"""

import os
import json
import subprocess
import sys

# Configuration paths
OUTPUT_VIDEO = "output/renders/final_output.mp4"
TIMESTAMPS_FILE = "data/timestamps.json"
THUMBNAIL_FILE = "output/renders/thumbnail_master.jpg"
AUDIO_FILE = "output/renders/final_audio.wav"

def check_file_exists(filepath, description):
    """Check if a file exists and return its size."""
    if not os.path.exists(filepath):
        return False, f"❌ {description} no encontrado: {filepath}"
    
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    return True, f"✅ {description}: {size_mb:.2f} MB"

def verify_video_integrity():
    """Verify video file integrity using ffprobe."""
    errors = []
    
    # Check existence
    exists, msg = check_file_exists(OUTPUT_VIDEO, "Video final")
    print(msg)
    
    if not exists:
        errors.append(msg)
        return errors
    
    # Check minimum size
    size_mb = os.path.getsize(OUTPUT_VIDEO) / (1024 * 1024)
    if size_mb < 2.0:
        errors.append(f"❌ El video es demasiado liviano ({size_mb:.2f} MB < 2MB). Podría estar corrupto.")
    
    # Get duration with ffprobe
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            OUTPUT_VIDEO
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and result.stdout.strip():
            duration = float(result.stdout.strip())
            print(f"✅ Duración del video: {duration:.2f} segundos ({duration/60:.2f} min)")
            
            # Warn if video is too short or too long
            if duration < 5:
                errors.append(f"⚠️ Video demasiado corto: {duration:.2f}s")
            elif duration > 600:  # 10 minutes
                print(f"⚠️ Video muy largo: {duration:.2f}s (asegúrate de que sea intencional)")
        else:
            errors.append("⚠️ No se pudo determinar la duración del video con ffprobe")
    except FileNotFoundError:
        errors.append("⚠️ ffprobe no está instalado. Instala ffmpeg para verificación completa.")
    except Exception as e:
        errors.append(f"⚠️ Error al verificar video: {e}")
    
    return errors

def verify_thumbnail():
    """Verify thumbnail exists and has correct dimensions."""
    errors = []
    
    exists, msg = check_file_exists(THUMBNAIL_FILE, "Miniatura")
    print(msg)
    
    if not exists:
        errors.append(msg)
        return errors
    
    # Check dimensions with PIL if available
    try:
        from PIL import Image
        with Image.open(THUMBNAIL_FILE) as img:
            width, height = img.size
            print(f"✅ Dimensiones miniatura: {width}x{height}px")
            
            if width != 1280 or height != 720:
                print(f"⚠️ La miniatura no tiene dimensiones 1280x720 recomendadas para YouTube")
    except ImportError:
        print("⚠️ Pillow no disponible para verificar dimensiones de miniatura")
    except Exception as e:
        errors.append(f"⚠️ Error al leer miniatura: {e}")
    
    return errors

def verify_timestamps():
    """Verify timestamps JSON file exists and contains valid data."""
    errors = []
    
    exists, msg = check_file_exists(TIMESTAMPS_FILE, "Archivo de timestamps")
    print(msg)
    
    if not exists:
        errors.append(msg)
        return errors
    
    try:
        with open(TIMESTAMPS_FILE, 'r') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            vehicle_count = len(data)
            print(f"✅ Timestamps registrados para {vehicle_count} vehículos")
            
            # Validate structure
            for i, item in enumerate(data):
                if not isinstance(item, dict):
                    errors.append(f"❌ Timestamp {i}: formato inválido (debe ser dict)")
                    continue
                
                required_keys = ['name', 'time']
                missing = [k for k in required_keys if k not in item]
                if missing:
                    errors.append(f"❌ Timestamp {i}: faltan claves {missing}")
                
        elif isinstance(data, dict):
            print(f"✅ Timestamps: {len(data)} entradas registradas")
        else:
            errors.append("❌ Formato de timestamps inválido")
            
    except json.JSONDecodeError as e:
        errors.append(f"❌ Error al parsear timestamps.json: {e}")
    except Exception as e:
        errors.append(f"❌ Error al leer timestamps: {e}")
    
    return errors

def verify_audio_streams():
    """Verify audio stream exists and is properly formatted."""
    errors = []
    
    # Check if audio file exists (optional, may be embedded in video)
    if os.path.exists(AUDIO_FILE):
        exists, msg = check_file_exists(AUDIO_FILE, "Audio WAV")
        print(msg)
    
    # Check audio stream in video
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_name,sample_rate,channels",
            "-of", "default=noprint_wrappers=1",
            OUTPUT_VIDEO
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split('\n')
            print(f"✅ Stream de audio detectado:")
            for line in lines:
                print(f"   {line}")
        else:
            errors.append("⚠️ No se detectó stream de audio en el video")
    except FileNotFoundError:
        pass  # ffprobe not available
    except Exception as e:
        errors.append(f"⚠️ Error al verificar audio: {e}")
    
    return errors

def verify_all():
    """Run all verification checks."""
    print("\n" + "="*60)
    print("🔍 INICIANDO CONTROL DE CALIDAD DEL PIPELINE...")
    print("="*60 + "\n")
    
    all_errors = []
    
    # Run all checks
    print("--- Verificando Video ---")
    all_errors.extend(verify_video_integrity())
    
    print("\n--- Verificando Miniatura ---")
    all_errors.extend(verify_thumbnail())
    
    print("\n--- Verificando Timestamps ---")
    all_errors.extend(verify_timestamps())
    
    print("\n--- Verificando Audio ---")
    all_errors.extend(verify_audio_streams())
    
    # Final report
    print("\n" + "="*60)
    if not all_errors:
        print("🎉 CONTROL DE CALIDAD EXITOSO: VIDEO 100% LISTO PARA YOUTUBE")
        print("="*60 + "\n")
        return 0
    else:
        print("🚨 SE DETECTARON PROBLEMAS:")
        for err in all_errors:
            print(f"  {err}")
        print("="*60)
        print("\n⚠️ Revisa los errores antes de subir a YouTube.\n")
        return 1

if __name__ == "__main__":
    sys.exit(verify_all())
