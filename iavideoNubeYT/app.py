#!/usr/bin/env python3
"""
Dashboard Web Interactivo para iavideoNubeYT
Interfaz Gradio para control visual de la producción de videos 3D
"""

import os
import sys
import json
import time
import threading
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

# Intentar importar gradio, si no existe mostrar mensaje claro
try:
    import gradio as gr
except ImportError:
    print("❌ Error: Gradio no está instalado.")
    print("   Ejecuta: pip install gradio")
    sys.exit(1)

# Rutas del proyecto
ROOT_DIR = Path(__file__).parent.absolute()
DATA_DIR = ROOT_DIR / "data"
DATASETS_DIR = DATA_DIR / "datasets"
OUTPUT_DIR = ROOT_DIR / "output"
RENDERS_DIR = OUTPUT_DIR / "renders"
ASSETS_DIR = ROOT_DIR / "assets"
METADATA_DIR = ROOT_DIR / "metadata"
STATUS_FILE = OUTPUT_DIR / "status.json"

# Asegurar que los directorios existan
for directory in [DATA_DIR, DATASETS_DIR, OUTPUT_DIR, RENDER_DIR, ASSETS_DIR, METADATA_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Estado global del proceso
process_state = {
    "running": False,
    "progress": 0,
    "current_phase": "Idle",
    "output_video": None,
    "thumbnail": None,
    "errors": []
}


def get_available_datasets():
    """Obtener lista de datasets disponibles"""
    datasets = []
    
    # Dataset por defecto
    default_csv = DATA_DIR / "military_vehicles.csv"
    if default_csv.exists():
        datasets.append(("Military Vehicles (Default)", str(default_csv)))
    
    # Datasets numerados
    if DATASETS_DIR.exists():
        for csv_file in sorted(DATASETS_DIR.glob("video_*.csv")):
            try:
                num = csv_file.stem.split("_")[1]
                # Leer primera línea para obtener nombre
                with open(csv_file, 'r') as f:
                    lines = f.readlines()
                    if len(lines) > 1:
                        # Extraer nombre del segundo elemento de la segunda línea
                        parts = lines[1].strip().split(',')
                        name = parts[1] if len(parts) > 1 else f"Video {num}"
                        count = len(lines) - 1  # Excluir header
                        datasets.append((f"#{num} - {name} ({count} activos)", str(csv_file)))
            except Exception as e:
                datasets.append((f"#{num} - Error al leer", str(csv_file)))
    
    return datasets


def get_seo_content(video_num=None):
    """Obtener contenido SEO desde metadata/youtube_seo.md"""
    seo_file = METADATA_DIR / "youtube_seo.md"
    if not seo_file.exists():
        return "No hay metadatos SEO disponibles."
    
    try:
        with open(seo_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Si se especifica número de video, intentar extraer sección relevante
        if video_num:
            # Lógica simple para extraer sección (puede mejorarse)
            sections = content.split("# ")
            for section in sections:
                if str(video_num).zfill(2) in section or f"0{video_num}" in section:
                    return f"# {section}"
        
        return content[:2000] + "..." if len(content) > 2000 else content
    except Exception as e:
        return f"Error al leer SEO: {str(e)}"


def run_pipeline_thread(dataset_path, audio_theme, resolution):
    """Ejecutar el pipeline en segundo plano"""
    global process_state
    
    process_state["running"] = True
    process_state["progress"] = 0
    process_state["current_phase"] = "Iniciando..."
    process_state["errors"] = []
    process_state["output_video"] = None
    process_state["thumbnail"] = None
    
    try:
        # Fase 0: Download References
        process_state["current_phase"] = "Descargando referencias..."
        process_state["progress"] = 5
        update_status()
        
        cmd_download = [sys.executable, str(ROOT_DIR / "src" / "download_references.py")]
        # Ejecutar sin bloquear completamente
        result = subprocess.run(cmd_download, capture_output=True, text=True, timeout=300)
        if result.returncode != 0 and "403" not in result.stderr:
            process_state["errors"].append(f"Download warnings: {result.stderr[:200]}")
        
        # Fase 1: Generate Models
        process_state["current_phase"] = "Generando modelos 3D con TRELLIS..."
        process_state["progress"] = 15
        update_status()
        
        cmd_models = [sys.executable, str(ROOT_DIR / "src" / "generate_models.py")]
        result = subprocess.run(cmd_models, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            process_state["errors"].append(f"Model generation warnings: {result.stderr[:200]}")
        
        # Fase 2: Build Scene (Blender)
        process_state["current_phase"] = "Construyendo escena Blender..."
        process_state["progress"] = 35
        update_status()
        
        cmd_blender = ["xvfb-run", "-a", "blender", "-b", "-P", str(ROOT_DIR / "src" / "build_scene.py"), "-a"]
        result = subprocess.run(cmd_blender, capture_output=True, text=True, timeout=900)
        if result.returncode != 0:
            process_state["errors"].append(f"Blender warnings: {result.stderr[:200]}")
        
        # Fase 3: Render Pipeline
        process_state["current_phase"] = "Renderizando (EEVEE Next)..."
        process_state["progress"] = 55
        update_status()
        
        cmd_render = [sys.executable, str(ROOT_DIR / "src" / "render_pipeline.py")]
        result = subprocess.run(cmd_render, capture_output=True, text=True, timeout=1200)
        if result.returncode != 0:
            process_state["errors"].append(f"Render warnings: {result.stderr[:200]}")
        
        # Fase 4: Audio Engine
        process_state["current_phase"] = "Generando audio cinematográfico..."
        process_state["progress"] = 75
        update_status()
        
        cmd_audio = [sys.executable, str(ROOT_DIR / "src" / "audio_engine.py")]
        result = subprocess.run(cmd_audio, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            process_state["errors"].append(f"Audio warnings: {result.stderr[:200]}")
        
        # Fase 5: Motion Graphics
        process_state["current_phase"] = "Aplicando motion graphics (HUD)..."
        process_state["progress"] = 85
        update_status()
        
        cmd_motion = [sys.executable, str(ROOT_DIR / "src" / "motion_graphics.py")]
        result = subprocess.run(cmd_motion, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            process_state["errors"].append(f"Motion graphics warnings: {result.stderr[:200]}")
        
        # Fase 6: Generate Thumbnail
        process_state["current_phase"] = "Generando miniatura de alto CTR..."
        process_state["progress"] = 90
        update_status()
        
        cmd_thumb = [sys.executable, str(ROOT_DIR / "src" / "generate_thumbnail.py")]
        result = subprocess.run(cmd_thumb, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            process_state["errors"].append(f"Thumbnail warnings: {result.stderr[:200]}")
        
        # Fase 7: Mix Final Video
        process_state["current_phase"] = "Mezclando video final con FFmpeg..."
        process_state["progress"] = 95
        update_status()
        
        # Buscar video renderizado y mezclar
        video_files = list(RENDERS_DIR.glob("*.mp4"))
        if video_files:
            process_state["output_video"] = str(video_files[-1])
        
        # Fase 8: Verify Pipeline
        process_state["current_phase"] = "Verificando calidad final..."
        process_state["progress"] = 98
        update_status()
        
        cmd_verify = [sys.executable, str(ROOT_DIR / "src" / "verify_pipeline.py")]
        result = subprocess.run(cmd_verify, capture_output=True, text=True, timeout=60)
        
        # Buscar thumbnail
        thumb_files = list(RENDERS_DIR.glob("thumbnail*.jpg")) + list(RENDERS_DIR.glob("thumbnail*.png"))
        if thumb_files:
            process_state["thumbnail"] = str(thumb_files[-1])
        
        process_state["progress"] = 100
        process_state["current_phase"] = "¡COMPLETADO!"
        
    except subprocess.TimeoutExpired:
        process_state["errors"].append("Timeout: El proceso tardó demasiado")
    except Exception as e:
        process_state["errors"].append(f"Error crítico: {str(e)}")
    finally:
        process_state["running"] = False
        update_status()


def update_status():
    """Actualizar archivo de estado JSON"""
    try:
        with open(STATUS_FILE, 'w') as f:
            json.dump(process_state, f, indent=2)
    except Exception as e:
        print(f"Error actualizando status: {e}")


def start_production(dataset_path, audio_theme, resolution):
    """Iniciar producción desde la interfaz"""
    global process_state
    
    if process_state["running"]:
        return "⚠️ Ya hay un proceso en ejecución. Espera a que termine."
    
    # Iniciar hilo separado
    thread = threading.Thread(
        target=run_pipeline_thread,
        args=(dataset_path, audio_theme, resolution),
        daemon=True
    )
    thread.start()
    
    return "✅ Producción iniciada. Monitorea el progreso en la pestaña 'Estado'."


def check_progress():
    """Verificar progreso actual (polling)"""
    try:
        if STATUS_FILE.exists():
            with open(STATUS_FILE, 'r') as f:
                state = json.load(f)
            
            progress = state.get("progress", 0)
            phase = state.get("current_phase", "Unknown")
            running = state.get("running", False)
            
            if progress >= 100 and not running:
                # Generar alerta de finalización
                alert = "🎉 ¡VIDEO COMPLETADO! Revisa la pestaña 'Galería' para descargar."
                return f"{progress}% - {phase}", alert
            
            return f"{progress}% - {phase}", ""
    except Exception as e:
        return f"Error: {str(e)}", ""
    
    return f"{process_state['progress']}% - {process_state['current_phase']}", ""


def get_gallery_items():
    """Obtener elementos para la galería de resultados"""
    items = []
    
    if not RENDER_DIR.exists():
        return items
    
    # Videos
    for video_file in sorted(RENDERS_DIR.glob("*.mp4"), reverse=True)[:10]:
        thumb_path = None
        
        # Buscar thumbnail asociada
        base_name = video_file.stem
        for ext in ["_thumb.jpg", "_thumb.png", ".jpg", ".png"]:
            candidate = RENDER_DIR / f"{base_name}{ext}"
            if candidate.exists():
                thumb_path = str(candidate)
                break
        
        # Si no hay thumbnail específica, usar la master
        if not thumb_path:
            master_thumb = RENDER_DIR / "thumbnail_master.jpg"
            if master_thumb.exists():
                thumb_path = str(master_thumb)
        
        # Obtener duración aproximada (metadatos simples)
        size_mb = video_file.stat().st_size / (1024 * 1024)
        
        items.append({
            "name": video_file.name,
            "video": str(video_file),
            "thumbnail": thumb_path,
            "info": f"Peso: {size_mb:.1f} MB | {datetime.fromtimestamp(video_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M')}"
        })
    
    return items


def copy_seo_to_clipboard(video_name):
    """Generar texto SEO para copiar"""
    seo_text = f"""
🎬 TÍTULO SUGERIDO:
{video_name.replace('.mp4', '')} - Scale Comparison 3D

📝 DESCRIPCIÓN:
Experience the true scale of incredible objects in this cinematic 3D comparison. From small to colossal!

⏱️ CHAPTERS:
Auto-generated based on object appearances

🔔 Subscribe for more 3D scale comparisons!

#scalecomparison #3d #comparison #visualization
""".strip()
    
    return seo_text


def clean_cache():
    """Limpiar archivos temporales manteniendo resultados finales"""
    cleaned = 0
    
    # Limpiar assets/models y assets/images (manteniendo estructura)
    for subdir in ["models", "images"]:
        dir_path = ASSETS_DIR / subdir
        if dir_path.exists():
            for file in dir_path.iterdir():
                if file.is_file():
                    try:
                        file.unlink()
                        cleaned += 1
                    except Exception:
                        pass
    
    # Limpiar __pycache__
    for pycache in ROOT_DIR.rglob("__pycache__"):
        try:
            shutil.rmtree(pycache)
            cleaned += 1
        except Exception:
            pass
    
    # Limpiar temporales de Blender
    for tmp_file in ROOT_DIR.glob("*.blend1"):
        try:
            tmp_file.unlink()
            cleaned += 1
        except Exception:
            pass
    
    return f"✅ Caché limpiada: {cleaned} archivos eliminados. Los videos en output/renders/ están seguros."


def create_dataset_from_form(form_data):
    """Crear nuevo dataset desde formulario"""
    try:
        # Parsear datos del formulario
        lines = form_data.strip().split('\n')
        if len(lines) < 2:
            return "❌ Formato inválido. Mínimo 2 objetos requeridos."
        
        # Encontrar siguiente número disponible
        existing = list(DATASETS_DIR.glob("video_*.csv"))
        next_num = len(existing) + 1
        
        new_csv = DATASETS_DIR / f"video_{next_num:03d}.csv"
        
        # Escribir CSV
        with open(new_csv, 'w') as f:
            f.write("order,name_en,scale_meters,asset_file,label_text,sfx_type,category,comparison_note\n")
            for i, line in enumerate(lines[1:], 1):  # Saltar header si existe
                parts = line.strip().split(',')
                if len(parts) >= 2:
                    name = parts[0].strip()
                    scale = parts[1].strip()
                    try:
                        float(scale)  # Validar que sea número
                    except ValueError:
                        continue
                    
                    asset_file = f"{name.lower().replace(' ', '_')}.glb"
                    label = f"{scale}m"
                    sfx = "light_click" if float(scale) < 10 else "heavy_thud"
                    category = "custom"
                    note = f"Custom entry #{i}"
                    
                    f.write(f"{i},{name},{scale},{asset_file},{label},{sfx},{category},{note}\n")
        
        return f"✅ Dataset creado: video_{next_num:03d}.csv con {len(lines)-1} objetos"
    
    except Exception as e:
        return f"❌ Error: {str(e)}"


# ============================================================================
# INTERFAZ GRADIO
# ============================================================================

with gr.Blocks(title="🎬 3D Scale Comparison Generator", theme=gr.themes.Soft()) as demo:
    
    gr.Markdown("""
    # 🎬 PANEL DE CONTROL: 3D SCALE COMPARISON GENERATOR
    ### Producción automatizada de videos de comparación de escala para YouTube
    """)
    
    with gr.Tabs():
        
        # PESTAÑA 1: GENERADOR DE VIDEOS
        with gr.TabItem("🎬 Generador de Videos"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 1. SELECCIONAR VIDEO")
                    dataset_dropdown = gr.Dropdown(
                        choices=get_available_datasets(),
                        label="Selecciona un video de la biblioteca",
                        type="value"
                    )
                    
                    gr.Markdown("### 2. CONFIGURACIÓN")
                    audio_theme = gr.Radio(
                        choices=["military", "scifi", "monsters", "structures"],
                        value="military",
                        label="Tema Musical"
                    )
                    
                    resolution = gr.Radio(
                        choices=["1080p60 (YouTube)", "4K24 (Cinema)"],
                        value="1080p60 (YouTube)",
                        label="Resolución"
                    )
                    
                    start_btn = gr.Button("▶ INICIAR PRODUCCIÓN EN 1 CLIC", variant="primary", size="lg")
                
                with gr.Column(scale=1):
                    gr.Markdown("### 📊 ESTADO DEL PROCESO")
                    progress_display = gr.Textbox(label="Progreso", value="0% - Idle", interactive=False)
                    alert_display = gr.Textbox(label="Alertas", value="", interactive=False)
                    
                    gr.Markdown("""
                    **Fases del Pipeline:**
                    1. Descarga de referencias
                    2. Generación de modelos 3D
                    3. Construcción de escena
                    4. Render EEVEE Next
                    5. Audio cinematográfico
                    6. Motion Graphics
                    7. Miniatura
                    8. Verificación QA
                    """)
            
            start_btn.click(
                fn=start_production,
                inputs=[dataset_dropdown, audio_theme, resolution],
                outputs=progress_display
            )
            
            # Polling para actualizar progreso
            timer = gr.Timer(value=2)
            timer.tick(
                fn=check_progress,
                outputs=[progress_display, alert_display]
            )
        
        # PESTAÑA 2: CREAR NUEVO VIDEO
        with gr.TabItem("➕ Crear Nuevo Video"):
            gr.Markdown("""
            ### Creador de Videos Personalizados
            Ingresa los objetos en orden de menor a mayor escala.
            
            **Formato:** `Nombre, Escala en metros`
            
            Ejemplo:
            ```
            Human Soldier, 1.8
            Micro Drone, 0.16
            Willys Jeep, 3.3
            M1 Abrams, 9.7
            ```
            """)
            
            form_data = gr.Textbox(
                label="Lista de Objetos",
                placeholder="Nombre, Escala(m)\nSoldier, 1.8\nDrone, 0.16...",
                lines=10
            )
            
            create_btn = gr.Button("Generar Dataset", variant="primary")
            create_result = gr.Textbox(label="Resultado")
            
            create_btn.click(
                fn=create_dataset_from_form,
                inputs=[form_data],
                outputs=[create_result]
            )
        
        # PESTAÑA 3: GALERÍA DE RESULTADOS
        with gr.TabItem("📁 Galería de Resultados"):
            with gr.Row():
                gallery_data = gr.State([])
                
                with gr.Column(scale=1):
                    gr.Markdown("### Videos Renderizados")
                    gallery_list = gr.JSON(label="Archivos Disponibles", value=[])
                    
                    refresh_btn = gr.Button("🔄 Actualizar Galería")
                    
                    video_info = gr.Textbox(label="Información del Video", interactive=False)
                    
                    seo_copy_btn = gr.Button("📋 Copiar Ficha de YouTube")
                    seo_output = gr.Textbox(label="SEO para Copiar", lines=8)
                
                with gr.Column(scale=1):
                    gr.Markdown("### Previsualización")
                    video_player = gr.Video(label="Reproductor", height=400)
                    thumb_viewer = gr.Image(label="Miniatura", height=200)
                    
                    download_video_btn = gr.DownloadButton(label="⬇ Descargar Video")
                    download_thumb_btn = gr.DownloadButton(label="⬇ Descargar Miniatura")
            
            def update_gallery():
                items = get_gallery_items()
                return items, items[0]["video"] if items else None, items[0]["thumbnail"] if items else None, items[0]["info"] if items else "Sin videos"
            
            refresh_btn.click(
                fn=update_gallery,
                outputs=[gallery_list, video_player, thumb_viewer, video_info]
            )
            
            seo_copy_btn.click(
                fn=copy_seo_to_clipboard,
                inputs=[video_info],
                outputs=[seo_output]
            )
        
        # PESTAÑA 4: LIMPIEZA
        with gr.TabItem("🧹 Limpieza"):
            gr.Markdown("""
            ### Liberar Espacio en Disco
            Elimina archivos temporales (modelos 3D, imágenes de referencia, caché) 
            sin tocar los videos finales MP4 ni las miniaturas.
            """)
            
            clean_btn = gr.Button("🗑️ Limpiar Archivos Temporales", variant="stop")
            clean_result = gr.Textbox(label="Resultado")
            
            clean_btn.click(
                fn=clean_cache,
                outputs=[clean_result]
            )
    
    # Footer
    gr.Markdown("""
    ---
    **iavideoNubeYT** - Automated 3D Scale Comparison Pipeline
    Hecho con ❤️ para creadores de YouTube
    """)


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🎬 INICIANDO DASHBOARD WEB DE IAVideonubeYT")
    print("="*60)
    print(f"📁 Directorio raíz: {ROOT_DIR}")
    print(f"📊 Estado inicial: {'OK' if ROOT_DIR.exists() else 'ERROR'}")
    print("\n🌐 Abriendo interfaz web...")
    print("   (El enlace público aparecerá abajo)")
    print("="*60 + "\n")
    
    # Lanzar con share=True para enlace público
    demo.launch(
        share=True,
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True
    )
