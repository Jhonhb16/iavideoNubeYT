#!/usr/bin/env python3
"""
Dashboard Web Interactivo para iavideoNubeYT
Interfaz Gradio para control visual de la producción de videos 3D
"""

import os
import re
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
for directory in [DATA_DIR, DATASETS_DIR, OUTPUT_DIR, RENDERS_DIR, ASSETS_DIR, METADATA_DIR]:
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
    """
    Ejecutar el pipeline en segundo plano delegando en run_all.sh.

    Antes esta función reimplementaba el pipeline llamando script por script,
    lo que provocaba dos problemas graves:
      1. Se saltaba todo lo que run_all.sh orquesta (semilla de variación,
         quemado de overlays, rutas explícitas, limpieza de temporales).
      2. Cada fase tenía timeout corto (render: 20 min). Un render real de
         ~3400 frames tarda horas y era abortado a mitad de camino.
    Ahora run_all.sh es la única fuente de verdad y se transmite su salida.
    """
    global process_state

    process_state["running"] = True
    process_state["progress"] = 0
    process_state["current_phase"] = "Verificando sistema..."
    process_state["errors"] = []
    process_state["output_video"] = None
    process_state["thumbnail"] = None
    process_state["log_tail"] = []
    update_status()

    # Mapa de frases del log -> progreso aproximado
    fases = [
        ("Phase 0", "Descargando referencias...", 5),
        ("Phase 1", "Generando modelos 3D...", 15),
        ("Phase 2", "Construyendo escena Blender...", 30),
        ("Rendering image sequence", "Renderizando fotogramas...", 45),
        ("Converting sequence", "Ensamblando video...", 75),
        ("Phase 3", "Generando audio cinematográfico...", 80),
        ("Phase 4", "Aplicando motion graphics (HUD)...", 85),
        ("Phase 5", "Generando miniatura...", 90),
        ("Phase 6", "Mezclando audio final...", 95),
    ]

    try:
        script = ROOT_DIR / "run_all.sh"
        if not script.exists():
            process_state["errors"].append(f"No se encontró {script}")
            return

        env = os.environ.copy()
        if dataset_path:
            env["IAVIDEO_VARIANT_SEED"] = Path(str(dataset_path)).stem
        if audio_theme:
            env["IAVIDEO_AUDIO_THEME"] = str(audio_theme)

        cmd = ["bash", str(script), "--resolution", str(resolution or "1080p")]

        process_state["current_phase"] = "Ejecutando pipeline..."
        update_status()

        proc = subprocess.Popen(
            cmd, cwd=str(ROOT_DIR), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )
        process_state["pid"] = proc.pid

        # Sin timeout: un render largo es legítimo. Se transmite el progreso.
        for linea in proc.stdout:
            linea = linea.rstrip()
            if not linea:
                continue

            cola = process_state.setdefault("log_tail", [])
            cola.append(linea)
            del cola[:-40]   # conservar solo las últimas 40 líneas

            for marca, etiqueta, pct in fases:
                if marca in linea:
                    process_state["current_phase"] = etiqueta
                    process_state["progress"] = pct
                    break

            # Progreso fino durante el render de fotogramas
            m = re.search(r"frame \d+ — (\d+)/(\d+)", linea)
            if m:
                hechos, total = int(m.group(1)), int(m.group(2))
                if total:
                    process_state["progress"] = 45 + int(30 * hechos / total)
                    process_state["current_phase"] = (
                        f"Renderizando fotograma {hechos}/{total}")

            if "[ERROR]" in linea or "Traceback" in linea:
                process_state["errors"].append(linea[:300])

            update_status()

        codigo = proc.wait()

        if codigo != 0:
            process_state["errors"].append(
                f"El pipeline terminó con código {codigo}. "
                f"Revisa el registro para el detalle.")
            process_state["current_phase"] = "Falló"
            process_state["progress"] = 0
        else:
            videos = sorted(RENDERS_DIR.glob("*.mp4"), key=os.path.getmtime) \
                if RENDERS_DIR.exists() else []
            if not videos:
                videos = sorted(OUTPUT_DIR.glob("**/*.mp4"), key=os.path.getmtime) \
                    if 'OUTPUT_DIR' in globals() and OUTPUT_DIR.exists() else []
            if videos:
                process_state["output_video"] = str(videos[-1])
                process_state["progress"] = 100
                process_state["current_phase"] = "¡COMPLETADO!"
            else:
                process_state["errors"].append(
                    "El pipeline terminó sin errores pero no se encontró "
                    "ningún video de salida.")
                process_state["current_phase"] = "Terminó sin salida"

            miniaturas = (list(RENDERS_DIR.glob("thumbnail*.jpg")) +
                          list(RENDERS_DIR.glob("thumbnail*.png"))) \
                if RENDERS_DIR.exists() else []
            if miniaturas:
                process_state["thumbnail"] = str(miniaturas[-1])

    except Exception as e:
        process_state["errors"].append(f"Error crítico: {e}")
        process_state["current_phase"] = "Falló"
    finally:
        process_state["running"] = False
        process_state["pid"] = None
        update_status()


def update_status():
    """Actualizar archivo de estado JSON"""
    try:
        with open(STATUS_FILE, 'w') as f:
            json.dump(process_state, f, indent=2)
    except Exception as e:
        print(f"Error actualizando status: {e}")


def normalizar_resolucion(valor):
    """
    La interfaz muestra etiquetas legibles ("1080p60 (YouTube)") pero
    run_all.sh solo acepta "1080p" o "4K". Sin esta traducción el script
    recibe un valor inválido.
    """
    texto = str(valor or "")
    return "4K" if "4K" in texto or "4k" in texto else "1080p"


def preflight_check(resolution="1080p"):
    """
    Verificación previa obligatoria antes de cualquier render largo.

    Existe porque el modo de fallo más caro del pipeline es silencioso:
    un pod con GPU que renderiza en CPU factura a precio de GPU durante
    horas sin que nada avise. Esto lo detecta ANTES de arrancar.

    Devuelve (bloqueante, reporte_markdown, detalles).
    'bloqueante' es True cuando hay un problema que hace inviable el render.
    """
    resolution = normalizar_resolucion(resolution)
    lines = []
    blocking = False
    details = {}

    # --- Blender presente ---
    blender = shutil.which("blender")
    if blender:
        try:
            ver = subprocess.run([blender, "--version"], capture_output=True,
                                 text=True, timeout=60).stdout.split("\n")[0]
        except Exception:
            ver = "versión desconocida"
        lines.append(f"✅ **Blender**: {ver}")
        details["blender"] = ver
    else:
        lines.append("❌ **Blender**: no encontrado en el PATH")
        blocking = True
        details["blender"] = None

    # --- FFmpeg ---
    if shutil.which("ffmpeg"):
        lines.append("✅ **FFmpeg**: disponible")
    else:
        lines.append("❌ **FFmpeg**: no encontrado — no se podrá ensamblar el video")
        blocking = True

    # --- Dependencias Python ---
    faltantes = []
    for mod in ("trimesh", "numpy", "PIL", "requests"):
        try:
            __import__(mod)
        except ImportError:
            faltantes.append(mod)
    if faltantes:
        lines.append(f"❌ **Dependencias Python**: faltan {', '.join(faltantes)}")
        lines.append("   → `pip install trimesh numpy Pillow requests`")
        blocking = True
    else:
        lines.append("✅ **Dependencias Python**: completas")

    # --- Espacio en disco ---
    try:
        libre_gb = shutil.disk_usage(str(ROOT_DIR)).free / (1024 ** 3)
        necesario = 25 if resolution == "4K" else 10
        if libre_gb < necesario:
            lines.append(f"❌ **Disco**: {libre_gb:.1f} GB libres "
                         f"(se recomiendan {necesario} GB para {resolution})")
            blocking = True
        else:
            lines.append(f"✅ **Disco**: {libre_gb:.1f} GB libres")
        details["disk_gb"] = round(libre_gb, 1)
    except Exception as e:
        lines.append(f"⚠️ **Disco**: no se pudo verificar ({e})")

    # --- GPU: la verificación que más importa ---
    gpu_script = ROOT_DIR / "src" / "gpu_check.py"
    if blender and gpu_script.exists():
        try:
            r = subprocess.run([blender, "-b", "-P", str(gpu_script)],
                               capture_output=True, text=True, timeout=180)
            salida = r.stdout
            details["gpu_output"] = salida[-3000:]

            software = any(m in salida.lower()
                           for m in ("llvmpipe", "swrast", "softpipe",
                                     "software rasterizer"))
            if r.returncode == 0 and not software:
                lines.append("✅ **GPU**: contexto por hardware confirmado — "
                             "EEVEE renderizará en GPU")
                details["gpu_ok"] = True
            else:
                lines.append("⚠️ **GPU**: NO se detectó contexto de hardware")
                lines.append("   → EEVEE renderizará en **CPU** (mucho más lento).")
                lines.append("   → Si estás en un pod con GPU, estás pagando GPU "
                             "por velocidad de CPU.")
                lines.append("   → Causa habitual: lanzar Blender con `xvfb-run`. "
                             "Usa contexto EGL en su lugar.")
                details["gpu_ok"] = False
                # Advertencia fuerte, pero no bloquea: en Colab/CPU es legítimo
        except subprocess.TimeoutExpired:
            lines.append("⚠️ **GPU**: la verificación excedió el tiempo límite")
            details["gpu_ok"] = None
        except Exception as e:
            lines.append(f"⚠️ **GPU**: no se pudo verificar ({e})")
            details["gpu_ok"] = None
    else:
        lines.append("⚠️ **GPU**: verificación no disponible")
        details["gpu_ok"] = None

    encabezado = ("### ❌ Hay problemas que impiden el render\n\n" if blocking
                  else "### ✅ Sistema listo\n\n")
    return blocking, encabezado + "\n\n".join(lines), details


def run_preflight_ui(resolution):
    """Wrapper del preflight para el botón de la interfaz."""
    _, reporte, _ = preflight_check(resolution)
    return reporte



def start_production(dataset_path, audio_theme, resolution, forzar_cpu=False):
    """
    Iniciar producción desde la interfaz.

    Antifallos: el preflight se ejecuta SIEMPRE y de forma automática, sin
    depender de que alguien recuerde correrlo. Si detecta un problema
    bloqueante, la producción no arranca. Si detecta que no hay GPU, exige
    una confirmación explícita antes de gastar horas de cómputo.
    """
    global process_state

    if process_state["running"]:
        return "⚠️ Ya hay un proceso en ejecución. Espera a que termine."

    resolution = normalizar_resolucion(resolution)
    bloqueante, reporte, detalles = preflight_check(resolution)

    if bloqueante:
        return (reporte + "\n\n---\n\n"
                "🛑 **Producción cancelada.** Corrige los puntos marcados "
                "con ❌ y vuelve a intentarlo.")

    if detalles.get("gpu_ok") is False and not forzar_cpu:
        return (reporte + "\n\n---\n\n"
                "🛑 **Producción detenida: no hay GPU por hardware.**\n\n"
                "Un render completo son ~3.400 fotogramas. En CPU esto tarda "
                "horas y, si estás en un pod de pago, cuesta dinero sin dar "
                "velocidad a cambio.\n\n"
                "Si aun así quieres continuar (por ejemplo, una prueba corta "
                "en Colab), marca **«Renderizar en CPU de todos modos»** "
                "y vuelve a pulsar el botón.")

    thread = threading.Thread(
        target=run_pipeline_thread,
        args=(dataset_path, audio_theme, resolution),
        daemon=True
    )
    thread.start()

    aviso = ""
    if detalles.get("gpu_ok") is False:
        aviso = "\n\n⚠️ Ejecutando en **CPU** por confirmación explícita."

    return (reporte + "\n\n---\n\n"
            "▶️ **Producción iniciada.** Monitorea el avance abajo." + aviso)


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
                    
                    gr.Markdown("### 3. VERIFICACIÓN")
                    forzar_cpu = gr.Checkbox(
                        value=False,
                        label="Renderizar en CPU de todos modos",
                        info="Solo para pruebas cortas. Un render completo en "
                             "CPU tarda horas."
                    )
                    check_btn = gr.Button("🔍 Verificar sistema", variant="secondary")

                    start_btn = gr.Button("▶ INICIAR PRODUCCIÓN EN 1 CLIC", variant="primary", size="lg")
                    gr.Markdown(
                        "_La verificación se ejecuta automáticamente al iniciar; "
                        "no hace falta recordarla._"
                    )
                
                with gr.Column(scale=1):
                    gr.Markdown("### 📊 ESTADO DEL PROCESO")
                    progress_display = gr.Textbox(label="Progreso", value="0% - Idle", interactive=False)
                    alert_display = gr.Textbox(label="Alertas", value="", interactive=False)
                    preflight_display = gr.Markdown(
                        value="_Pulsa «Verificar sistema» o inicia la producción "
                              "para ver el estado._"
                    )
                    
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
            
            check_btn.click(
                fn=run_preflight_ui,
                inputs=[resolution],
                outputs=preflight_display
            )

            start_btn.click(
                fn=start_production,
                inputs=[dataset_dropdown, audio_theme, resolution, forzar_cpu],
                outputs=preflight_display
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
