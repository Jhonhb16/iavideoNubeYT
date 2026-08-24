#!/bin/bash
# ============================================================================
# SCRIPT DE INICIO DEL DASHBOARD WEB
# iavideoNubeYT - Interfaz Gráfica para Producción de Videos 3D
# ============================================================================

set -e

echo ""
echo "============================================================"
echo "  🎬 IAVideonubeYT - Dashboard Web Launcher"
echo "============================================================"
echo ""

# Verificar que app.py existe
if [ ! -f "app.py" ]; then
    echo "❌ Error: app.py no encontrado en el directorio actual"
    echo "   Asegúrate de estar en la raíz del repositorio iavideoNubeYT"
    exit 1
fi

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 no está instalado"
    exit 1
fi

# Verificar e instalar gradio si es necesario
echo "📦 Verificando dependencias..."
if ! python3 -c "import gradio" &> /dev/null; then
    echo "   Instalando Gradio (esto puede tardar 1-2 minutos)..."
    pip install gradio --quiet
fi

# Verificar xvfb para Blender headless
if ! command -v xvfb-run &> /dev/null; then
    echo "   Instalando xvfb para renderizado headless..."
    apt-get update -qq && apt-get install -y -qq xvfb > /dev/null 2>&1 || true
fi

echo ""
echo "✅ Dependencias verificadas"
echo ""
echo "🌐 Iniciando servidor web..."
echo "   Espera unos segundos hasta que aparezca el enlace público"
echo ""
echo "============================================================"
echo ""

# Ejecutar app.py con xvfb para asegurar compatibilidad con Blender
xvfb-run -a python3 app.py
