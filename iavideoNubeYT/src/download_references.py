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
import time
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


def _build_headers(url: str) -> dict:
    """
    Build request headers appropriate for the host.

    Wikimedia blocks generic/spoofed browser User-Agents and returns 429.
    Their policy requires a descriptive UA identifying the tool and a contact.
    Override the contact via the IAVIDEO_CONTACT environment variable.
    """
    contact = os.environ.get('IAVIDEO_CONTACT', 'https://github.com/Jhonhb16/iavideoNubeYT')
    wikimedia_ua = f'iavideoNubeYT/1.0 ({contact}) python-requests'

    if 'wikimedia.org' in url or 'wikipedia.org' in url:
        return {
            'User-Agent': wikimedia_ua,
            'Accept': 'image/*,*/*;q=0.8',
            'Api-User-Agent': wikimedia_ua,
        }

    return {
        'User-Agent': wikimedia_ua,
        'Accept': 'image/*,*/*;q=0.8',
    }


def resolve_pixabay_url(url: str) -> str:
    """
    Resolve a Pixabay CDN URL into a downloadable URL via the Pixabay API.

    Direct hotlinking to cdn.pixabay.com is blocked by design (HTTP 403);
    the official API must be used instead. Set PIXABAY_API_KEY to enable.

    Returns the resolved URL, or the original URL when no key is configured.
    """
    if 'pixabay.com' not in url:
        return url

    api_key = os.environ.get('PIXABAY_API_KEY')
    if not api_key:
        print("  ℹ Pixabay URL detected but PIXABAY_API_KEY is not set "
              "(direct CDN hotlinking returns 403). Skipping API resolution.")
        return url

    # Derive a search term from the CDN filename, e.g.
    # .../soldier-557946_1280.png -> "soldier"
    try:
        filename = url.rstrip('/').split('/')[-1]
        query = filename.split('-')[0].split('_')[0]

        resp = requests.get(
            'https://pixabay.com/api/',
            params={
                'key': api_key,
                'q': query,
                'image_type': 'photo',
                'per_page': 3,
            },
            timeout=30,
        )
        resp.raise_for_status()
        hits = resp.json().get('hits', [])

        if hits:
            resolved = hits[0].get('largeImageURL') or hits[0].get('webformatURL')
            if resolved:
                print(f"  ✓ Pixabay API resolved '{query}'")
                return resolved

        print(f"  ⚠ Pixabay API returned no results for '{query}'")
    except Exception as e:
        print(f"  ⚠ Pixabay API error: {e}")

    return url


def download_image(url: str, output_path: Path, timeout: int = 30,
                   max_retries: int = 4, base_delay: float = 1.5) -> bool:
    """
    Download an image from URL and save it, with exponential backoff.

    Retries on HTTP 429 (rate limit) and 5xx errors, honouring the
    Retry-After header when the server provides one.

    Args:
        url: Image URL to download
        output_path: Path to save the downloaded image
        timeout: Request timeout in seconds
        max_retries: Number of attempts before giving up
        base_delay: Base seconds for exponential backoff (delay = base * 2**n)

    Returns:
        True if download successful, False otherwise
    """
    url = resolve_pixabay_url(url)
    headers = _build_headers(url)

    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=timeout, stream=True)

            # Retry on rate limiting / transient server errors
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < max_retries - 1:
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        try:
                            delay = float(retry_after)
                        except ValueError:
                            delay = base_delay * (2 ** attempt)
                    else:
                        delay = base_delay * (2 ** attempt)

                    print(f"  ⏳ HTTP {response.status_code} — retrying in "
                          f"{delay:.1f}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue

            response.raise_for_status()

            # Verify it's an image
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
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
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                print(f"  ⏳ Timeout — retrying in {delay:.1f}s "
                      f"(attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
                continue
            print(f"⚠ Timeout downloading {url}")
            return False
        except requests.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                print(f"  ⏳ Connection error — retrying in {delay:.1f}s "
                      f"(attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
                continue
            print(f"⚠ Connection error downloading {url}")
            return False
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else '?'
            print(f"⚠ HTTP error {status} for {url}")
            if status == 403 and 'pixabay' in url:
                print("  → Pixabay blocks direct CDN hotlinking. "
                      "Set PIXABAY_API_KEY to use the official API.")
            return False
        except requests.exceptions.RequestException as e:
            print(f"⚠ Request error downloading {url}: {e}")
            return False
        except Exception as e:
            print(f"⚠ Unexpected error downloading {url}: {e}")
            return False

    print(f"⚠ Failed after {max_retries} attempts: {url}")
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

            # Be polite between requests: hammering Wikimedia with 15 rapid
            # requests is what triggers HTTP 429 in the first place.
            time.sleep(float(os.environ.get('IAVIDEO_DOWNLOAD_DELAY', '1.0')))
    
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
