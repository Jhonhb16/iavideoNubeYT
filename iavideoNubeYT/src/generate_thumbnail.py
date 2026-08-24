#!/usr/bin/env python3
"""
generate_thumbnail.py
Generador de miniaturas automáticas de Alto CTR para YouTube.
Estilo: MetaBallStudios / RED SIDE - Alto contraste, elementos tácticos, texto de impacto.

Features:
- Lienzo 1280x720 (16:9) optimizado para YouTube
- Fondo con degradado cinemático y cuadrícula táctica
- Silueta humana de referencia (1.8m) con círculo de atención
- Badge de escala "1.8m vs 337m" en rojo alerta
- Texto principal con borde grueso para máxima legibilidad
- Corrección de color y viñeta sutil
"""

import os
import sys
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

# Configuración de directorios
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
OUTPUT_DIR = os.path.abspath(os.path.join(ROOT_DIR, "output/renders"))
ASSETS_DIR = os.path.abspath(os.path.join(ROOT_DIR, "assets/images"))
FONTS_DIR = os.path.abspath(os.path.join(ROOT_DIR, "assets/fonts"))

# Asegurar que los directorios existan
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(FONTS_DIR, exist_ok=True)

def download_font():
    """Descarga Roboto-Bold si no existe."""
    font_path = os.path.join(FONTS_DIR, "font.ttf")
    if not os.path.exists(font_path):
        print("⬇️ Descargando fuente Roboto-Bold...")
        try:
            import urllib.request
            url = "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Bold.ttf"
            urllib.request.urlretrieve(url, font_path)
            print(f"✅ Fuente descargada en: {font_path}")
        except Exception as e:
            print(f"⚠️ No se pudo descargar la fuente: {e}")
            print("   Usando fuente por defecto del sistema.")
    return font_path

def create_tactical_grid(draw, width, height):
    """Dibuja un fondo con degradado y cuadrícula táctica en perspectiva."""
    # Degradado oscuro cinemático (azul/negro profundo)
    for y in range(height):
        # Gradiente vertical: más oscuro arriba, ligeramente más claro abajo
        ratio = y / height
        r = int(12 + (25 * ratio))
        g = int(14 + (28 * ratio))
        b = int(18 + (35 * ratio))
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Líneas de cuadrícula de suelo en perspectiva (efecto 3D)
    horizon_y = int(height * 0.62)  # Línea del horizonte
    
    # Línea de horizonte brillante (cian neón)
    draw.line([(0, horizon_y), (width, horizon_y)], fill=(0, 220, 255), width=2)
    
    # Líneas verticales en perspectiva
    center_x = width // 2
    for x in range(0, width, 60):
        # Proyectar líneas desde el centro hacia abajo
        x_offset = x - center_x
        x_bottom = center_x + int(x_offset * 2.5)
        if 0 <= x_bottom <= width:
            alpha = min(255, int(abs(x_offset) / 2))
            draw.line([(x, horizon_y), (x_bottom, height)], fill=(50 + alpha, 60 + alpha, 80 + alpha), width=1)
    
    # Líneas horizontales de cuadrícula (espaciado logarítmico para profundidad)
    for i in range(1, 8):
        y_pos = int(horizon_y + (i ** 1.8) * 8)
        if y_pos < height:
            alpha = int(200 * (i / 8))
            draw.line([(0, y_pos), (width, y_pos)], fill=(40, 50, 70, alpha), width=1)

def add_text_with_outline(draw, text, position, font, fill_color, outline_color, outline_width=3):
    """Añade texto con contorno grueso para máxima legibilidad."""
    x, y = position
    # Dibujar contorno en 8 direcciones
    for dx, dy in [(-outline_width, 0), (outline_width, 0), 
                   (0, -outline_width), (0, outline_width),
                   (-outline_width, -outline_width), (outline_width, outline_width),
                   (-outline_width, outline_width), (outline_width, -outline_width)]:
        draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
    # Texto principal
    draw.text((x, y), text, font=font, fill=fill_color)

def create_high_ctr_thumbnail(vehicle_name="PANZER MAUS", vehicle_scale="337m", human_scale="1.8m"):
    """
    Genera una miniatura de alto CTR (Click-Through Rate).
    
    Args:
        vehicle_name: Nombre del vehículo principal
        vehicle_scale: Escala del vehículo grande
        human_scale: Escala de referencia humana
    """
    print("🎨 Generando miniatura de alto CTR...")
    
    # 1. Crear lienzo base 16:9 (1280x720)
    thumb = Image.new("RGB", (1280, 720), color=(12, 14, 18))
    draw = ImageDraw.Draw(thumb)
    
    # 2. Dibujar fondo táctico
    create_tactical_grid(draw, 1280, 720)
    
    # 3. Cargar y procesar activos (Soldado de referencia)
    soldier_path = os.path.join(ASSETS_DIR, "soldier.png")
    soldier_img = None
    
    if os.path.exists(soldier_path):
        try:
            soldier = Image.open(soldier_path).convert("RGBA")
            # Redimensionar manteniendo aspect ratio
            soldier.thumbnail((200, 200), Image.Resampling.LANCZOS)
            soldier_img = soldier
            # Posicionar en esquina inferior izquierda
            soldier_x, soldier_y = 80, 480
            thumb.paste(soldier, (soldier_x, soldier_y), soldier)
            print(f"✅ Soldado cargado desde: {soldier_path}")
        except Exception as e:
            print(f"⚠️ Error cargando soldado: {e}")
    
    # Si no hay imagen del soldado, dibujar silueta placeholder
    if soldier_img is None:
        # Silueta humana simplificada
        draw.rectangle([(100, 500), (140, 680)], fill=(180, 180, 180))
        draw.ellipse([(110, 470), (130, 500)], fill=(180, 180, 180))  # Cabeza
        print("ℹ️ Usando silueta placeholder para humano")
    
    # Círculo de atención amarillo alrededor del soldado (efecto foco)
    draw.ellipse([(60, 460), (180, 700)], outline=(255, 220, 0), width=5)
    # Brillo exterior
    draw.ellipse([(55, 455), (185, 705)], outline=(255, 100, 0), width=2)
    
    # 4. Badge de escala ("1.8m vs 337m") - Esquina superior izquierda
    badge_width = 480
    badge_height = 90
    badge_x, badge_y = 40, 40
    
    # Fondo rojo alerta con gradiente
    for i in range(badge_height):
        r = int(220 + (35 * (i / badge_height)))
        g = int(20 + (30 * (i / badge_height)))
        b = int(20 + (30 * (i / badge_height)))
        draw.line([(badge_x, badge_y + i), (badge_x + badge_width, badge_y + i)], 
                  fill=(r, g, b))
    
    # Borde blanco del badge
    draw.rectangle([(badge_x, badge_y), (badge_x + badge_width, badge_y + badge_height)], 
                   outline=(255, 255, 255), width=3)
    
    # Texto del badge
    font_path = download_font()
    try:
        font_badge = ImageFont.truetype(font_path, 42)
    except:
        font_badge = ImageFont.load_default()
    
    scale_text = f"{human_scale} vs {vehicle_scale}"
    # Sombra del texto
    draw.text((badge_x + 15, badge_y + 20), scale_text, fill=(0, 0, 0), font=font_badge)
    # Texto principal blanco
    draw.text((badge_x + 12, badge_y + 17), scale_text, fill=(255, 255, 255), font=font_badge)
    
    # 5. Texto principal de impacto ("HOW BIG?" o nombre del vehículo)
    font_path = download_font()
    try:
        font_large = ImageFont.truetype(font_path, 88)
        font_medium = ImageFont.truetype(font_path, 52)
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
    
    # Texto central dramático
    main_text = "SIZE COMPARISON"
    sub_text = vehicle_name.upper()
    
    # Posición centrada-derecha
    text_x, text_y = 520, 180
    
    # Añadir texto principal con contorno negro grueso
    add_text_with_outline(draw, main_text, (text_x, text_y), 
                         font_large, (255, 230, 0), (0, 0, 0), outline_width=4)
    
    # Subtítulo con nombre del vehículo
    add_text_with_outline(draw, sub_text, (text_x, text_y + 90), 
                         font_medium, (255, 255, 255), (0, 0, 0), outline_width=3)
    
    # 6. Elementos decorativos adicionales (flechas, indicadores)
    # Flecha de crecimiento
    arrow_start = (350, 600)
    arrow_end = (900, 600)
    draw.line([arrow_start, arrow_end], fill=(255, 50, 50), width=8)
    # Punta de flecha
    draw.polygon([(880, 580), (920, 600), (880, 620)], fill=(255, 50, 50))
    # Etiqueta de la flecha
    draw.text((600, 560), "SCALE GROWTH", fill=(255, 200, 0), font=font_medium)
    
    # 7. Viñeta sutil para enfoque cinematográfico
    overlay = Image.new('RGBA', thumb.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for r in range(100, 0, -10):
        alpha = int(100 * (1 - r/100))
        overlay_draw.rounded_rectangle(
            [(r, r), (1280-r, 720-r)], 
            radius=20, 
            fill=(0, 0, 0, alpha)
        )
    thumb = Image.alpha_composite(thumb.convert("RGBA"), overlay).convert("RGB")
    
    # 8. Mejorar contraste y saturación
    enhancer = ImageEnhance.Contrast(thumb)
    thumb = enhancer.enhance(1.25)  # +25% contraste
    enhancer = ImageEnhance.Color(thumb)
    thumb = enhancer.enhance(1.15)  # +15% saturación
    
    # 9. Guardar archivo final
    output_filename = "thumbnail_master.jpg"
    out_path = os.path.join(OUTPUT_DIR, output_filename)
    thumb.save(out_path, "JPEG", quality=95, optimize=True, progressive=True)
    
    print(f"✅ Miniatura generada exitosamente: {out_path}")
    print(f"   Dimensiones: 1280x720 (16:9)")
    print(f"   Formato: JPEG (calidad 95%)")
    
    return out_path

if __name__ == "__main__":
    # Valores por defecto (Panzer Maus como ejemplo)
    vehicle_name = "PANZER MAUS"
    vehicle_scale = "337m"
    human_scale = "1.8m"
    
    # Permitir argumentos desde línea de comandos
    if len(sys.argv) > 1:
        vehicle_name = sys.argv[1]
    if len(sys.argv) > 2:
        vehicle_scale = sys.argv[2]
    if len(sys.argv) > 3:
        human_scale = sys.argv[3]
    
    create_high_ctr_thumbnail(vehicle_name, vehicle_scale, human_scale)
