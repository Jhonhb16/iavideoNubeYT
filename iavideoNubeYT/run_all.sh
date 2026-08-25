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
    python3 -c "import numpy, PIL, tqdm, trimesh" 2>/dev/null || {
        log_warning "Some Python packages missing. Installing from requirements.txt..."
        pip install -q trimesh numpy Pillow tqdm 2>/dev/null || \
            log_warning "Install failed. Run manually: pip install -r requirements.txt"
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

download_references() {
    log_info "Phase 0: Downloading reference images..."
    
    cd "$SCRIPT_DIR"
    python3 "$SRC_DIR/download_references.py"
    
    if [ $? -eq 0 ]; then
        log_success "Reference images downloaded successfully"
    else
        log_warning "Some reference images failed to download (placeholders created)"
    fi
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

build_scene_and_setup_camera() {
    log_info "Phase 2: Building Blender scene and setting up camera rig..."
    
    cd "$SCRIPT_DIR"
    
    # Check if Blender is available
    if command -v blender &> /dev/null; then
        # Build scene with camera rig integrated and timestamps export
        blender -b -P "$SRC_DIR/build_scene.py" -- \
            --csv "$DATA_DIR/military_vehicles.csv" \
            --timestamps "$DATA_DIR/timestamps.json"
        
        if [ $? -eq 0 ]; then
            log_success "Scene built successfully with camera animation"
            
            # Verify timestamps were generated
            if [ -f "$DATA_DIR/timestamps.json" ]; then
                log_success "Timestamps exported to: $DATA_DIR/timestamps.json"
            else
                log_warning "Timestamps file not generated"
            fi
        else
            log_error "Scene building failed"
            return 1
        fi
    else
        log_warning "Blender not available. Scene building skipped."
        log_warning "You can run this step manually when Blender is installed."
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
    
    log_info "Phase 3: Generating cinematic audio with audio_engine.py..."
    
    cd "$SCRIPT_DIR"
    
    # Use timestamps from Blender for precise sync
    TIMESTAMPS_FILE="$DATA_DIR/timestamps.json"
    
    if [ -f "$TIMESTAMPS_FILE" ]; then
        log_info "Using timestamps from: $TIMESTAMPS_FILE"
        python3 "$SRC_DIR/audio_engine.py" \
            --csv "$DATA_DIR/military_vehicles.csv" \
            --timestamps "$TIMESTAMPS_FILE" \
            --output-dir "$ASSETS_DIR/audio"
    else
        log_warning "Timestamps file not found, using auto-calculated duration"
        
        # Calculate approximate video duration based on number of objects
        NUM_OBJECTS=$(tail -n +2 "$DATA_DIR/military_vehicles.csv" | wc -l)
        VIDEO_DURATION=$((NUM_OBJECTS * 5))  # ~5 seconds per object
        
        python3 "$SRC_DIR/audio_engine.py" \
            --csv "$DATA_DIR/military_vehicles.csv" \
            --duration "$VIDEO_DURATION" \
            --output-dir "$ASSETS_DIR/audio"
    fi
    
    if [ $? -eq 0 ]; then
        log_success "Audio generated successfully"
    else
        log_warning "Audio generation had issues"
    fi
}

motion_graphics() {
    log_info "Phase 4: Generating motion graphics overlays..."
    
    cd "$SCRIPT_DIR"

    RENDERED_VIDEO="$OUTPUT_DIR/scale_comparison_${RESOLUTION}_${QUALITY}.mp4"
    OVERLAY_VIDEO="$OUTPUT_DIR/scale_comparison_overlaid.mp4"

    # Build the per-frame overlay sequence (counter + shrinking human reference)
    python3 "$SRC_DIR/motion_graphics.py" \
        --sequence \
        --csv "$DATA_DIR/military_vehicles.csv" \
        --timestamps "$DATA_DIR/timestamps.json" \
        --output-dir "$ASSETS_DIR/graphics" \
        --fonts-dir "$ASSETS_DIR/fonts"

    if [ $? -ne 0 ]; then
        log_warning "Overlay sequence generation failed; continuing without overlays"
        return 0
    fi

    # Burn the sequence onto the rendered video. Without this step the
    # overlays are generated to disk and never reach the final video.
    if [ ! -f "$RENDERED_VIDEO" ]; then
        log_warning "No rendered video at $RENDERED_VIDEO; skipping overlay burn"
        return 0
    fi

    python3 "$SRC_DIR/motion_graphics.py" \
        --apply-to-video "$RENDERED_VIDEO" \
        --output-video "$OVERLAY_VIDEO" \
        --csv "$DATA_DIR/military_vehicles.csv" \
        --timestamps "$DATA_DIR/timestamps.json" \
        --output-dir "$ASSETS_DIR/graphics" \
        --fonts-dir "$ASSETS_DIR/fonts"

    if [ $? -eq 0 ] && [ -f "$OVERLAY_VIDEO" ]; then
        # The overlaid video becomes the input for the audio mix
        mv -f "$OVERLAY_VIDEO" "$RENDERED_VIDEO"
        log_success "Motion graphics burned into video"

        # Overlay frames are ~0.15 GB per video; clean unless explicitly kept
        if [ "${IAVIDEO_KEEP_FRAMES}" != "1" ]; then
            rm -rf "$ASSETS_DIR/graphics/sequence"
        fi
    else
        log_warning "Overlay burn failed; continuing with un-overlaid video"
    fi
}

mix_final_video() {
    log_info "Phase 6: Mixing final video with audio..."
    
    cd "$SCRIPT_DIR"
    
    # Explicit path: never discover the input with `ls -t`, which can silently
    # pick up a stale video from a previous run when the render fails.
    RENDERED_VIDEO="$OUTPUT_DIR/scale_comparison_${RESOLUTION}_${QUALITY}.mp4"
    FINAL_VIDEO="$OUTPUT_DIR/final_scale_comparison.mp4"

    if [ ! -f "$RENDERED_VIDEO" ]; then
        log_warning "Expected rendered video not found: $RENDERED_VIDEO"
        log_warning "Skipping audio mix (render step likely failed)."
        return 1
    fi

    # Guard against re-muxing a stale file: the render must be newer than
    # any existing final video.
    if [ -f "$FINAL_VIDEO" ] && [ "$FINAL_VIDEO" -nt "$RENDERED_VIDEO" ]; then
        log_warning "Existing final video is newer than the render."
        log_warning "Render likely failed. Aborting mix to avoid publishing stale output."
        return 1
    fi

    log_info "Mixing audio with: $RENDERED_VIDEO"
    
    # Get video duration
    VIDEO_DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$RENDERED_VIDEO" 2>/dev/null || echo "30")
    
    # Generate audio matching video duration if needed
    python3 "$SRC_DIR/generate_audio.py" \
        --duration "$VIDEO_DURATION" \
        --transitions "5,10,15,20,25" \
        --markers "0,5,10,15,20" \
        --output "$ASSETS_DIR/audio" \
        --mix-with-video "$RENDERED_VIDEO" \
        --output-video "$FINAL_VIDEO"
    
    if [ $? -eq 0 ]; then
        log_success "Final video created: $FINAL_VIDEO"
    else
        log_warning "Audio mixing failed. Video without audio available at: $RENDERED_VIDEO"
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
    
    # Phase 0: Download reference images
    download_references
    
    generate_models
    build_scene_and_setup_camera
    render_video
    generate_audio
    motion_graphics
    
    # Phase 5: Generate thumbnail
    log_info "Phase 5: Generating high-CTR thumbnail..."
    cd "$SCRIPT_DIR"
    python3 "$SRC_DIR/generate_thumbnail.py"
    if [ $? -eq 0 ]; then
        log_success "Thumbnail generated successfully"
    else
        log_warning "Thumbnail generation failed"
    fi
    
    mix_final_video
    
    # Phase 6: Quality Assurance Verification
    log_info "Phase 6: Running quality assurance checks..."
    cd "$SCRIPT_DIR"
    python3 "$SRC_DIR/verify_pipeline.py"
    
    print_summary
}

# Run main function
main "$@"
