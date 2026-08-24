#!/bin/bash
# ============================================================================
# SCRIPT MAESTRO DE CONFIGURACIÓN E INICIO
# iavideoNubeYT - Instalación automática y lanzamiento del dashboard
# ============================================================================

set -e

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  🎬 IAVideonubeYT - Setup & Start Master Script          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para imprimir estado
print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

# ============================================================================
# FASE 0: PRE-FLIGHT CHECK
# ============================================================================
echo "🔍 FASE 0: Ejecutando Pre-Flight Check..."
echo ""

if [ -f "src/preflight_check.py" ]; then
    python3 src/preflight_check.py || print_warning "Algunas verificaciones fallaron, continuando..."
else
    print_warning "preflight_check.py no encontrado, saltando verificación"
fi

echo ""

# ============================================================================
# FASE 1: INSTALAR PAQUETES DEL SISTEMA
# ============================================================================
echo "📦 FASE 1: Instalando paquetes del sistema..."

# Actualizar repositorios
apt-get update -qq

# Instalar dependencias críticas
DEPS="ffmpeg libgl1-mesa-glx libxi6 libgconf-2-4 libfontconfig1 xvfb wget build-essential git"
for pkg in $DEPS; do
    if dpkg -l | grep -q "^ii  $pkg "; then
        print_status "$pkg ya está instalado"
    else
        echo "   Instalando $pkg..."
        apt-get install -y -qq $pkg > /dev/null 2>&1 && print_status "$pkg instalado" || print_warning "No se pudo instalar $pkg"
    fi
done

echo ""

# ============================================================================
# FASE 2: VERIFICAR/INSTALAR BLENDER
# ============================================================================
echo "🎨 FASE 2: Verificando Blender 4.2..."

if command -v blender &> /dev/null; then
    BLEND_VER=$(blender --version | head -n1)
    print_status "Blender detectado: $BLEND_VER"
else
    print_warning "Blender no encontrado en PATH"
    echo "   Intentando descargar Blender 4.2 LTS..."
    
    BLEND_URL="https://download.blender.org/release/Blender4.2/blender-4.2.0-linux-x64.tar.xz"
    BLEND_DIR="/opt/blender"
    
    if [ ! -d "$BLEND_DIR" ]; then
        wget -q "$BLEND_URL" -O /tmp/blender.tar.xz && \
        tar -xf /tmp/blender.tar.xz -C /opt/ && \
        ln -sf /opt/blender-4.2.0-linux-x64/blender /usr/local/bin/blender && \
        print_status "Blender 4.2 instalado correctamente" || \
        print_error "No se pudo instalar Blender automáticamente"
    fi
fi

echo ""

# ============================================================================
# FASE 3: INSTALAR DEPENDENCIAS PYTHON
# ============================================================================
echo "🐍 FASE 3: Instalando dependencias de Python..."

if [ -f "requirements.txt" ]; then
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
    print_status "Dependencias Python instaladas"
else
    print_warning "requirements.txt no encontrado"
fi

# Verificar gradio específicamente
if ! python3 -c "import gradio" &> /dev/null 2>&1; then
    echo "   Instalando Gradio para el dashboard..."
    pip install gradio -q
    print_status "Gradio instalado"
fi

echo ""

# ============================================================================
# FASE 4: VALIDAR ESTRUCTURA DE DIRECTORIOS
# ============================================================================
echo "📁 FASE 4: Validando estructura de directorios..."

REQUIRED_DIRS="data assets output metadata src"
for dir in $REQUIRED_DIRS; do
    if [ -d "$dir" ]; then
        print_status "Directorio $dir/ existe"
    else
        mkdir -p "$dir" && print_status "Directorio $dir/ creado"
    fi
done

# Crear subdirectorios críticos
mkdir -p data/datasets
mkdir -p assets/models
mkdir -p assets/images
mkdir -p assets/audio/{military,scifi,monsters}
mkdir -p output/renders

print_status "Estructura de directorios lista"

echo ""

# ============================================================================
# FASE 5: LANZAR DASHBOARD WEB
# ============================================================================
echo "🚀 FASE 5: Lanzando Dashboard Web..."
echo ""
echo "============================================================"
echo "  El servidor web se iniciará en breve..."
echo "  Busca el enlace público que comienza con:"
echo "  https://xxxx.gradio.live"
echo "============================================================"
echo ""

# Ejecutar dashboard con xvfb para compatibilidad headless
if command -v xvfb-run &> /dev/null; then
    xvfb-run -a python3 app.py
else
    python3 app.py
fi
