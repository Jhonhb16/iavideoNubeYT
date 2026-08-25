#!/bin/bash
# ============================================================================
# setup_linode_gpu.sh
# Provisiona una VM GPU de Linode/Akamai para iavideoNubeYT
#
# Uso:
#   PASO 1:  bash setup_linode_gpu.sh drivers    -> instala drivers y REINICIA
#   PASO 2:  bash setup_linode_gpu.sh app        -> instala Blender, repo y deps
#   PASO 3:  bash setup_linode_gpu.sh verify     -> comprueba que la GPU sirve
#
# Se divide en pasos porque los drivers NVIDIA EXIGEN un reinicio antes de
# poder usarse. Intentar hacerlo todo seguido falla siempre.
# ============================================================================

set -euo pipefail

REPO_URL="https://github.com/Jhonhb16/iavideoNubeYT.git"
BLENDER_VER="4.2.0"
BLENDER_DIR="/opt/blender-${BLENDER_VER}-linux-x64"
WORK_DIR="/root/iavideoNubeYT"

verde()  { echo -e "\033[0;32m$1\033[0m"; }
rojo()   { echo -e "\033[0;31m$1\033[0m"; }
azul()   { echo -e "\033[0;34m$1\033[0m"; }

# ---------------------------------------------------------------------------
# PASO 1: drivers NVIDIA + bibliotecas EGL
# ---------------------------------------------------------------------------
paso_drivers() {
    azul "=== PASO 1/3: drivers NVIDIA y EGL ==="

    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq \
        build-essential wget curl git unzip \
        software-properties-common ubuntu-drivers-common

    azul "Instalando drivers NVIDIA (esto tarda varios minutos)..."
    ubuntu-drivers autoinstall || {
        rojo "autoinstall falló; intentando el paquete del servidor..."
        apt-get install -y -qq nvidia-driver-550-server
    }

    # EGL: lo que permite a Blender usar la GPU SIN servidor X.
    # Sin esto hay que recurrir a xvfb, que renderiza por software (CPU).
    azul "Instalando bibliotecas EGL..."
    apt-get install -y -qq \
        libegl1 libegl-mesa0 libglvnd0 libgl1 libglx0 \
        libgles2 libopengl0 \
        libxi6 libxxf86vm1 libxfixes3 libxrender1 libsm6 libice6 \
        ffmpeg fonts-dejavu-core python3-pip xz-utils

    verde ""
    verde "✓ Drivers instalados."
    rojo  "!! HAY QUE REINICIAR AHORA. Ejecuta:"
    echo  ""
    echo  "      reboot"
    echo  ""
    echo  "  Espera ~60s, vuelve a entrar por SSH y ejecuta:"
    echo  "      bash setup_linode_gpu.sh app"
    echo  ""
}

# ---------------------------------------------------------------------------
# PASO 2: Blender, repositorio y dependencias
# ---------------------------------------------------------------------------
paso_app() {
    azul "=== PASO 2/3: Blender, repo y dependencias ==="

    # Comprobar que el driver quedó activo tras el reinicio
    if ! command -v nvidia-smi &>/dev/null; then
        rojo "✗ nvidia-smi no existe. El PASO 1 no terminó bien."
        exit 1
    fi
    if ! nvidia-smi &>/dev/null; then
        rojo "✗ nvidia-smi falla. ¿Reiniciaste después del PASO 1?"
        echo "  Ejecuta 'reboot' y vuelve a intentarlo."
        exit 1
    fi
    verde "✓ GPU detectada por el sistema:"
    nvidia-smi --query-gpu=name,memory.total,driver_version \
               --format=csv,noheader | sed 's/^/    /'

    # --- Blender ---
    if [ ! -d "$BLENDER_DIR" ]; then
        azul "Descargando Blender ${BLENDER_VER}..."
        cd /opt
        wget -q "https://download.blender.org/release/Blender4.2/blender-${BLENDER_VER}-linux-x64.tar.xz"
        tar -xf "blender-${BLENDER_VER}-linux-x64.tar.xz"
        rm "blender-${BLENDER_VER}-linux-x64.tar.xz"
    fi

    # Lanzador SIN xvfb: en esta VM sí hay GPU real, así que se usa EGL.
    cat > /usr/local/bin/blender << EOF
#!/bin/bash
export BLENDER_ENABLE_EGL=1
export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json
exec ${BLENDER_DIR}/blender "\$@"
EOF
    chmod +x /usr/local/bin/blender
    verde "✓ Blender: $(blender --version 2>/dev/null | head -n1)"

    # --- Repositorio ---
    if [ -d "$WORK_DIR/.git" ]; then
        azul "Actualizando repositorio..."
        cd "$WORK_DIR" && git pull origin main
    else
        azul "Clonando repositorio..."
        git clone "$REPO_URL" "$WORK_DIR"
    fi

    # --- Dependencias Python ---
    azul "Instalando dependencias Python..."
    pip3 install -q --break-system-packages \
        trimesh numpy Pillow requests tqdm gradio

    chmod +x "$WORK_DIR/iavideoNubeYT/run_all.sh" 2>/dev/null || true
    chmod +x "$WORK_DIR/iavideoNubeYT/start_ui.sh" 2>/dev/null || true

    verde ""
    verde "✓ Instalación completa."
    echo  "  Siguiente paso:"
    echo  "      bash setup_linode_gpu.sh verify"
    echo  ""
}

# ---------------------------------------------------------------------------
# PASO 3: verificación
# ---------------------------------------------------------------------------
paso_verify() {
    azul "=== PASO 3/3: verificación de GPU ==="

    echo ""
    azul "--- Hardware ---"
    nvidia-smi --query-gpu=name,memory.total,driver_version \
               --format=csv,noheader | sed 's/^/    /'

    echo ""
    azul "--- Vendedores EGL registrados ---"
    ls -1 /usr/share/glvnd/egl_vendor.d/ 2>/dev/null | sed 's/^/    /' || \
        rojo "    ninguno (EGL no está configurado)"

    echo ""
    azul "--- Veredicto de Blender ---"
    cd "$WORK_DIR/iavideoNubeYT"
    if blender -b -P src/gpu_check.py; then
        verde ""
        verde "════════════════════════════════════════════════"
        verde " ✓ LISTO: EEVEE usará la GPU."
        verde "════════════════════════════════════════════════"
        echo ""
        echo "  Arranca el panel de control con:"
        echo "      cd $WORK_DIR/iavideoNubeYT && ./start_ui.sh"
        echo ""
    else
        rojo ""
        rojo "════════════════════════════════════════════════"
        rojo " ✗ EEVEE NO tiene contexto de GPU por hardware."
        rojo "════════════════════════════════════════════════"
        echo ""
        echo "  NO lances un render largo así: sería CPU a precio de GPU."
        echo "  Envíale a Claude toda la salida de arriba."
        echo ""
        exit 1
    fi
}

case "${1:-}" in
    drivers) paso_drivers ;;
    app)     paso_app ;;
    verify)  paso_verify ;;
    *)
        echo "Uso: bash setup_linode_gpu.sh {drivers|app|verify}"
        echo ""
        echo "  drivers  PASO 1 — drivers NVIDIA + EGL (requiere reboot después)"
        echo "  app      PASO 2 — Blender, repo y dependencias"
        echo "  verify   PASO 3 — comprobar que la GPU realmente sirve"
        exit 1
        ;;
esac
