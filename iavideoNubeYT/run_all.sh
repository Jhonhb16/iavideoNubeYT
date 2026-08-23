#!/bin/bash
# =============================================================================
# iavideoNubeYT - One-Click Master Execution Pipeline
# =============================================================================
# Automated 3D Scale Comparison Video Production for YouTube
# 
# Usage: ./run_all.sh [options]
# Options:
#   --resolution  1080p|4K (default: 1080p)
#   --quality     low|medium|high|ultra (default: high)
#   --skip-models Skip 3D model generation (use existing)
#   --skip-audio  Skip audio generation
#   --help        Show this help message
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$SCRIPT_DIR/src"
DATA_DIR="$SCRIPT_DIR/data"
ASSETS_DIR="$SCRIPT_DIR/assets"
OUTPUT_DIR="$SCRIPT_DIR/output/renders"

# Default parameters
RESOLUTION="1080p"
QUALITY="high"
SKIP_MODELS=false
SKIP_AUDIO=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --resolution)
            RESOLUTION="$2"
            shift 2
            ;;
        --quality)
            QUALITY="$2"
            shift 2
            ;;
        --skip-models)
            SKIP_MODELS=true
            shift
            ;;
        --skip-audio)
            SKIP_AUDIO=true
            shift
            ;;
        --help)
            echo -e "iavideoNubeYT - Automated 3D Scale Comparison Video Pipeline"
            echo ""
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --resolution  1080p|4K (default: 1080p)"
            echo "  --quality     low|medium|high|ultra (default: high)"
            echo "  --skip-models Skip 3D model generation (use existing)"
            echo "  --skip-audio  Skip audio generation"
            echo "  --help        Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    log_info "Checking dependencies..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 not found. Please install Python 3.10+"
        exit 1
    fi
    
    # Check Blender
    if ! command -v blender &> /dev/null; then
        log_warning "Blender not found in PATH. Please ensure Blender 4.2+ is installed."
        log_warning "Download from: https://www.blender.org/download/"
    else
        BLENDER_VERSION=$(blender --version | head -n1)
        log_success "Blender detected: $BLENDER_VERSION"
    fi
    
    # Check FFmpeg
    if ! command -v ffmpeg &> /dev/null; then
        log_warning "FFmpeg not found. Audio mixing will be unavailable."
        log_warning "Install with: sudo apt-get install ffmpeg"
    else
        FFMPEG_VERSION=$(ffmpeg -version | head -n1)
        log_success "FFmpeg detected: $FFMPEG_VERSION"
    fi
    
    # Check required Python packages
    log_info "Checking Python packages..."
    python3 -c "import numpy, PIL, tqdm" 2>/dev/null || {
        log_warning "Some Python packages missing. Run: pip install -r requirements.txt"
    }
}

create_directories() {
    log_info "Creating directory structure..."
    mkdir -p "$DATA_DIR"
    mkdir -p "$ASSETS_DIR/images"
    mkdir -p "$ASSETS_DIR/models"
    mkdir -p "$ASSETS_DIR/audio"
    mkdir -p "$OUTPUT_DIR"
    log_success "Directory structure ready"
}

generate_models() {
    if [ "$SKIP_MODELS" = true ]; then
        log_info "Skipping model generation (--skip-models flag set)"
        return 0
    fi
    
    log_info "Phase 1: Generating 3D models with TRELLIS..."
    
    cd "$SCRIPT_DIR"
    python3 "$SRC_DIR/generate_models.py" \
        --csv "$DATA_DIR/military_vehicles.csv" \
        --images-dir "$ASSETS_DIR/images" \
        --models-dir "$ASSETS_DIR/models" \
        --placeholders
    
    if [ $? -eq 0 ]; then
        log_success "3D models generated successfully"
    else
        log_error "Model generation failed"
        return 1
    fi
}

build_scene() {
    log_info "Phase 2: Building Blender scene..."
    
    cd "$SCRIPT_DIR"
    
    # Check if Blender is available
    if command -v blender &> /dev/null; then
        blender -b -P "$SRC_DIR/build_scene.py" -- "$DATA_DIR/military_vehicles.csv"
        
        if [ $? -eq 0 ]; then
            log_success "Scene built successfully"
        else
            log_error "Scene building failed"
            return 1
        fi
    else
        log_warning "Blender not available. Scene building skipped."
        log_warning "You can run this step manually when Blender is installed."
    fi
}

setup_camera_rig() {
    log_info "Phase 3: Setting up adaptive camera rig..."
    
    cd "$SCRIPT_DIR"
    
    if command -v blender &> /dev/null; then
        blender -b -P "$SRC_DIR/camera_rig.py"
        
        if [ $? -eq 0 ]; then
            log_success "Camera rig configured"
        else
            log_warning "Camera rig setup had issues"
        fi
    else
        log_warning "Blender not available. Camera rig setup skipped."
    fi
}

render_video() {
    log_info "Phase 4: Rendering video ($RESOLUTION, $QUALITY quality)..."
    
    cd "$SCRIPT_DIR"
    
    if command -v blender &> /dev/null; then
        blender -b -P "$SRC_DIR/render_pipeline.py" -- \
            --output "$OUTPUT_DIR" \
            --resolution "$RESOLUTION" \
            --quality "$QUALITY"
        
        if [ $? -eq 0 ]; then
            log_success "Video rendered successfully"
        else
            log_error "Rendering failed"
            return 1
        fi
    else
        log_warning "Blender not available. Rendering skipped."
    fi
}

generate_audio() {
    if [ "$SKIP_AUDIO" = true ]; then
        log_info "Skipping audio generation (--skip-audio flag set)"
        return 0
    fi
    
    log_info "Phase 5: Generating cinematic audio..."
    
    cd "$SCRIPT_DIR"
    
    # Calculate approximate video duration based on number of objects
    NUM_OBJECTS=$(tail -n +2 "$DATA_DIR/military_vehicles.csv" | wc -l)
    VIDEO_DURATION=$((NUM_OBJECTS * 5))  # ~5 seconds per object
    
    # Generate timestamps for transitions and markers
    TRANSITIONS=""
    MARKERS="0"
    for ((i=1; i<NUM_OBJECTS; i++)); do
        TS=$((i * 5))
        TRANSITIONS="$TRANSITIONS,$TS"
        MARKERS="$MARKERS,$TS"
    done
    
    python3 "$SRC_DIR/generate_audio.py" \
        --duration "$VIDEO_DURATION" \
        --transitions "$TRANSITIONS" \
        --markers "$MARKERS" \
        --output "$ASSETS_DIR/audio"
    
    if [ $? -eq 0 ]; then
        log_success "Audio generated successfully"
    else
        log_warning "Audio generation had issues"
    fi
}

mix_final_video() {
    log_info "Phase 6: Mixing final video with audio..."
    
    cd "$SCRIPT_DIR"
    
    # Find the most recent rendered video
    LATEST_VIDEO=$(ls -t "$OUTPUT_DIR"/*.mp4 2>/dev/null | head -n1)
    
    if [ -z "$LATEST_VIDEO" ]; then
        log_warning "No rendered video found for audio mixing"
        return 0
    fi
    
    log_info "Mixing audio with: $LATEST_VIDEO"
    
    # Get video duration
    VIDEO_DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$LATEST_VIDEO" 2>/dev/null || echo "30")
    
    # Generate audio matching video duration if needed
    python3 "$SRC_DIR/generate_audio.py" \
        --duration "$VIDEO_DURATION" \
        --transitions "5,10,15,20,25" \
        --markers "0,5,10,15,20" \
        --output "$ASSETS_DIR/audio" \
        --mix-with-video "$LATEST_VIDEO" \
        --output-video "$OUTPUT_DIR/final_scale_comparison.mp4"
    
    if [ $? -eq 0 ]; then
        log_success "Final video created: $OUTPUT_DIR/final_scale_comparison.mp4"
    else
        log_warning "Audio mixing failed. Video without audio available at: $LATEST_VIDEO"
    fi
}

print_summary() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}     PIPELINE EXECUTION COMPLETE       ${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "Output directory: ${BLUE}$OUTPUT_DIR${NC}"
    echo ""
    echo "Generated files:"
    ls -lh "$OUTPUT_DIR"/*.{mp4,mov,avi} 2>/dev/null || echo "  No video files found"
    echo ""
    echo -e "Next steps:"
    echo "  1. Review videos in: $OUTPUT_DIR"
    echo "  2. Upload to YouTube"
    echo "  3. Optimize title, description, and tags"
    echo ""
}

# Main execution
main() {
    echo -e "${BLUE}"
    echo "=========================================="
    echo "  iavideoNubeYT - Scale Comparison Pipeline"
    echo "==========================================${NC}"
    echo ""
    
    check_dependencies
    create_directories
    
    echo ""
    log_info "Starting pipeline execution..."
    echo ""
    
    generate_models
    build_scene
    setup_camera_rig
    render_video
    generate_audio
    mix_final_video
    
    print_summary
}

# Run main function
main "$@"
