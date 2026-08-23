#!/usr/bin/env python3
"""
Download References Script for iavideoNubeYT

Downloads reference images for all assets listed in military_vehicles.csv.
Generates solid placeholder images if URLs fail.

Usage:
    python3 src/download_references.py
"""

import os
import csv
import requests
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import io

# Configuration
SCRIPT_DIR = Path(__file__).parent.parent
DATA_DIR = SCRIPT_DIR / "data"
IMAGES_DIR = SCRIPT_DIR / "assets" / "images"
CSV_FILE = DATA_DIR / "military_vehicles.csv"

# Ensure directories exist
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Placeholder image settings
PLACEHOLDER_SIZE = (512, 512)
PLACEHOLDER_BG_COLOR = (255, 255, 255)  # White background
PLACEHOLDER_TEXT_COLOR = (64, 64, 64)   # Dark gray text


def create_placeholder_image(name: str, output_path: Path) -> bool:
    """
    Create a solid placeholder image with the asset name.
    
    Args:
        name: Asset name to display on placeholder
        output_path: Path to save the placeholder image
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create white background image
        img = Image.new('RGB', PLACEHOLDER_SIZE, color=PLACEHOLDER_BG_COLOR)
        draw = ImageDraw.Draw(img)
        
        # Try to use a default font, fall back to default if not available
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except (IOError, OSError):
            try:
                font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", 24)
            except (IOError, OSError):
                font = ImageFont.load_default()
        
        # Format text with proper wrapping
        label_parts = name.replace('_', ' ').title().split()
        lines = []
        current_line = ""
        
        for part in label_parts:
            test_line = f"{current_line} {part}".strip()
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] < PLACEHOLDER_SIZE[0] - 40:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = part
        
        if current_line:
            lines.append(current_line)
        
        # Calculate text position (centered)
        total_height = 0
        line_heights = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            height = bbox[3] - bbox[1]
            line_heights.append(height)
            total_height += height + 8  # 8px spacing between lines
        
        y_start = (PLACEHOLDER_SIZE[1] - total_height) // 2
        y_current = y_start
        
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = (PLACEHOLDER_SIZE[0] - text_width) // 2
            draw.text((x, y_current), line, fill=PLACEHOLDER_TEXT_COLOR, font=font)
            y_current += line_heights[i] + 8
        
        # Save as PNG
        img.save(output_path, 'PNG')
        print(f"✓ Created placeholder: {output_path.name}")
        return True
        
    except Exception as e:
        print(f"✗ Failed to create placeholder for {name}: {e}")
        return False


def download_image(url: str, output_path: Path, timeout: int = 30) -> bool:
    """
    Download an image from URL and save it.
    
    Args:
        url: Image URL to download
        output_path: Path to save the downloaded image
        timeout: Request timeout in seconds
        
    Returns:
        True if download successful, False otherwise
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=timeout, stream=True)
        response.raise_for_status()
        
        # Verify it's an image
        content_type = response.headers.get('content-type', '')
        if not content_type.startswith('image/'):
            # Try to open with PIL to verify
            try:
                img = Image.open(io.BytesIO(response.content))
                img.verify()
            except Exception:
                print(f"⚠ Invalid image content from {url}")
                return False
        
        # Save the image
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        # Verify saved file
        try:
            img = Image.open(output_path)
            img.verify()
            print(f"✓ Downloaded: {output_path.name} ({len(response.content)} bytes)")
            return True
        except Exception:
            print(f"⚠ Downloaded file is not a valid image: {output_path.name}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"⚠ Timeout downloading {url}")
        return False
    except requests.exceptions.ConnectionError:
        print(f"⚠ Connection error downloading {url}")
        return False
    except requests.exceptions.HTTPError as e:
        print(f"⚠ HTTP error {e.response.status_code} for {url}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"⚠ Request error downloading {url}: {e}")
        return False
    except Exception as e:
        print(f" Unexpected error downloading {url}: {e}")
        return False


def process_asset(asset_name: str, image_url: str) -> bool:
    """
    Process a single asset: download or create placeholder.
    
    Args:
        asset_name: Name of the asset
        image_url: URL to download the image from
        
    Returns:
        True if successful (download or placeholder created)
    """
    # Determine output filename
    output_filename = f"{asset_name}.png"
    output_path = IMAGES_DIR / output_filename
    
    # Skip if already exists
    if output_path.exists():
        print(f"⊘ Skipping {output_filename} (already exists)")
        return True
    
    # Try to download
    if download_image(image_url, output_path):
        return True
    
    # Fallback to placeholder
    print(f"→ Creating placeholder for {asset_name}")
    return create_placeholder_image(asset_name, output_path)


def main():
    """Main entry point."""
    print("=" * 60)
    print("iavideoNubeYT - Reference Image Downloader")
    print("=" * 60)
    print(f"Images directory: {IMAGES_DIR}")
    print(f"CSV file: {CSV_FILE}")
    print("=" * 60)
    
    # Check if CSV exists
    if not CSV_FILE.exists():
        print(f"✗ Error: CSV file not found at {CSV_FILE}")
        print("Please ensure military_vehicles.csv exists in the data/ directory.")
        return 1
    
    # Read CSV and process assets
    success_count = 0
    placeholder_count = 0
    skip_count = 0
    fail_count = 0
    
    with open(CSV_FILE, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        for row in reader:
            asset_name = row.get('name', '').strip()
            image_url = row.get('image_url', '').strip()
            
            if not asset_name:
                continue
            
            if not image_url:
                print(f"⚠ No image_url for {asset_name}, creating placeholder")
                output_path = IMAGES_DIR / f"{asset_name}.png"
                if not output_path.exists():
                    if create_placeholder_image(asset_name, output_path):
                        placeholder_count += 1
                continue
            
            # Check if already exists
            output_path = IMAGES_DIR / f"{asset_name}.png"
            if output_path.exists():
                print(f"⊘ Skipping {asset_name} (already exists)")
                skip_count += 1
                continue
            
            # Process asset
            if process_asset(asset_name, image_url):
                if (IMAGES_DIR / f"{asset_name}.png").exists():
                    # Check if it's a placeholder by file size (placeholders are small)
                    file_size = (IMAGES_DIR / f"{asset_name}.png").stat().st_size
                    if file_size < 5000:  # Placeholders are typically < 5KB
                        placeholder_count += 1
                    else:
                        success_count += 1
            else:
                fail_count += 1
    
    # Summary
    print("\n" + "=" * 60)
    print("Download Summary:")
    print("=" * 60)
    print(f"✓ Successfully downloaded: {success_count}")
    print(f"→ Placeholders created:    {placeholder_count}")
    print(f"⊘ Skipped (existed):       {skip_count}")
    print(f"✗ Failed:                  {fail_count}")
    print(f"Total processed:           {success_count + placeholder_count + skip_count + fail_count}")
    print("=" * 60)
    
    # List all images in directory
    print("\nImages in assets/images/:")
    images = sorted([f.name for f in IMAGES_DIR.iterdir() if f.suffix.lower() in ['.png', '.jpg', '.jpeg']])
    if images:
        for img in images:
            size = (IMAGES_DIR / img).stat().st_size
            print(f"  • {img} ({size:,} bytes)")
    else:
        print("  (no images found)")
    
    print("\n" + "=" * 60)
    
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    exit(main())
