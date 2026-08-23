"""
motion_graphics.py - Military HUD overlays and telemetry using FFmpeg + Pillow

Generates cinematic overlay layers for scale comparison videos:
- Modern TTF font download (Roboto-Bold)
- Tactical military HUD interface with gradient overlays
- Human silhouette reference (1.8m) with label
- Dynamic scale progress bar
- Country of origin, technical name, metrics (m/ft), estimated weight
- Color correction (contrast +15%, controlled saturation, vignette)
"""

import os
import sys
import json
import csv
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from pathlib import Path


class MotionGraphicsGenerator:
    """Generate military-style HUD overlays for scale comparison videos."""
    
    def __init__(self, output_dir="assets/graphics", fonts_dir="assets/fonts"):
        self.output_dir = Path(output_dir)
        self.fonts_dir = Path(fonts_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.fonts_dir.mkdir(parents=True, exist_ok=True)
        
        # Font settings
        self.font_path = self.fonts_dir / "font.ttf"
        self.font_url = "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Bold.ttf"
        
        # HUD colors (military tactical style)
        self.colors = {
            'bg_dark': (10, 15, 20, 220),
            'bg_gradient_start': (5, 8, 12, 200),
            'bg_gradient_end': (20, 25, 35, 180),
            'text_primary': (180, 220, 255, 255),
            'text_secondary': (100, 150, 200, 220),
            'text_accent': (0, 200, 255, 255),
            'progress_bar': (0, 180, 255, 255),
            'progress_bg': (30, 40, 50, 150),
            'grid_lines': (50, 80, 100, 80),
            'warning': (255, 100, 100, 255),
            'success': (100, 255, 150, 255)
        }
        
        # Video settings (will be updated from actual render)
        self.resolution = (1920, 1080)
        self.fps = 60
        
    def download_font(self):
        """Download Roboto-Bold font if not exists."""
        if not self.font_path.exists():
            print(f"Downloading font from {self.font_url}...")
            try:
                response = requests.get(self.font_url, timeout=30)
                response.raise_for_status()
                
                with open(self.font_path, 'wb') as f:
                    f.write(response.content)
                
                print(f"✓ Font downloaded to {self.font_path}")
                return True
            except Exception as e:
                print(f"⚠ Font download failed: {e}")
                print("  Using system font fallback...")
                # Try system fonts
                system_fonts = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "/usr/share/fonts/TITLE.txt",
                    "C:\\Windows\\Fonts\\arialbd.ttf",
                    "/System/Library/Fonts/Helvetica.ttc"
                ]
                
                for font_path in system_fonts:
                    if os.path.exists(font_path):
                        self.font_path = Path(font_path)
                        print(f"  Using system font: {font_path}")
                        return True
                
                return False
        else:
            print(f"✓ Font already exists: {self.font_path}")
            return True
    
    def get_font(self, size=24):
        """Load font at specified size."""
        try:
            return ImageFont.truetype(str(self.font_path), size)
        except Exception:
            return ImageFont.load_default()
    
    def create_gradient_overlay(self, width, height, direction='vertical'):
        """Create semi-transparent dark gradient overlay for text readability."""
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        if direction == 'vertical':
            # Bottom gradient for lower third info panel
            for y in range(height // 3):
                alpha = int(180 * (1 - y / (height // 3)))
                color = (*self.colors['bg_gradient_end'][:3], alpha)
                draw.line([(0, height - y), (width, height - y)], fill=color)
        elif direction == 'horizontal':
            # Top gradient for progress bar
            for x in range(width):
                alpha = int(150 * (x / width))
                color = (*self.colors['bg_gradient_start'][:3], alpha)
                draw.line([(x, 0), (x, height // 4)], fill=color)
        
        return overlay
    
    def create_human_silhouette(self, height=120):
        """Create human silhouette reference (1.8m scale)."""
        # Create silhouette image
        silo_width = height // 3
        silhouette = Image.new('RGBA', (silo_width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(silhouette)
        
        # Simple human figure (head, body, legs)
        head_size = height // 8
        body_width = silo_width // 2
        body_height = height // 3
        leg_height = height // 3
        
        # Head (circle)
        head_x = silo_width // 2 - head_size // 2
        head_y = 10
        draw.ellipse(
            [head_x, head_y, head_x + head_size, head_y + head_size],
            fill=self.colors['text_secondary']
        )
        
        # Body (rectangle)
        body_x = silo_width // 2 - body_width // 2
        body_y = head_y + head_size
        draw.rectangle(
            [body_x, body_y, body_x + body_width, body_y + body_height],
            fill=self.colors['text_secondary']
        )
        
        # Legs (two rectangles)
        leg_width = body_width // 2
        left_leg_x = body_x
        right_leg_x = body_x + body_width - leg_width
        legs_y = body_y + body_height
        
        draw.rectangle(
            [left_leg_x, legs_y, left_leg_x + leg_width, legs_y + leg_height],
            fill=self.colors['text_secondary']
        )
        draw.rectangle(
            [right_leg_x, legs_y, right_leg_x + leg_width, legs_y + leg_height],
            fill=self.colors['text_secondary']
        )
        
        # Add glow effect
        silhouette = silhouette.filter(ImageFilter.GaussianBlur(radius=1))
        
        return silhouette
    
    def create_scale_progress_bar(self, width, current_index, total_objects, vehicle_name):
        """Create dynamic scale progress bar showing current position."""
        bar_height = 60
        progress_img = Image.new('RGBA', (width, bar_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(progress_img)
        
        # Background
        margin = 40
        bar_width = width - (margin * 2)
        bar_y = 15
        
        # Draw background track
        draw.rounded_rectangle(
            [margin, bar_y, margin + bar_width, bar_y + 20],
            radius=10,
            fill=self.colors['progress_bg']
        )
        
        # Draw progress fill
        progress_ratio = (current_index + 1) / total_objects
        fill_width = int(bar_width * progress_ratio)
        draw.rounded_rectangle(
            [margin, bar_y, margin + fill_width, bar_y + 20],
            radius=10,
            fill=self.colors['progress_bar']
        )
        
        # Draw markers for each vehicle
        marker_spacing = bar_width / max(1, total_objects - 1) if total_objects > 1 else 0
        font_small = self.get_font(12)
        
        for i in range(total_objects):
            marker_x = margin + int(i * marker_spacing) if total_objects > 1 else margin + bar_width // 2
            
            # Marker dot
            dot_radius = 6 if i <= current_index else 4
            dot_color = self.colors['text_accent'] if i <= current_index else self.colors['text_secondary']
            draw.ellipse(
                [marker_x - dot_radius, bar_y - dot_radius, 
                 marker_x + dot_radius, bar_y + 20 + dot_radius],
                fill=dot_color
            )
        
        # Vehicle name label
        font_medium = self.get_font(18)
        label = f"VEHICLE {current_index + 1}/{total_objects}: {vehicle_name.upper()}"
        
        # Calculate text bounding box for centering
        bbox = draw.textbbox((0, 0), label, font=font_medium)
        text_width = bbox[2] - bbox[0]
        text_x = (width - text_width) // 2
        text_y = bar_y + 35
        
        draw.text((text_x, text_y), label, font=font_medium, fill=self.colors['text_primary'])
        
        return progress_img
    
    def create_info_panel(self, vehicle_data, width, height):
        """Create lower-third info panel with vehicle telemetry."""
        panel_height = 180
        panel = Image.new('RGBA', (width, panel_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(panel)
        
        # Background gradient
        gradient = self.create_gradient_overlay(width, panel_height, 'vertical')
        panel.alpha_composite(gradient)
        
        # Left section: Human silhouette reference
        silo = self.create_human_silhouette(height=100)
        panel.paste(silo, (30, panel_height - 110), silo)
        
        # Human label
        font_small = self.get_font(14)
        draw.text((30, panel_height - 25), "HUMAN 1.8m", 
                  font=font_small, fill=self.colors['text_secondary'])
        
        # Center section: Vehicle info
        margin_left = 180
        y_base = panel_height - 140
        
        # Vehicle name (large)
        font_large = self.get_font(32)
        vehicle_name = vehicle_data.get('name', 'UNKNOWN').replace('_', ' ').upper()
        draw.text((margin_left, y_base), vehicle_name, 
                  font=font_large, fill=self.colors['text_accent'])
        
        # Technical specs
        font_medium = self.get_font(20)
        font_small = self.get_font(16)
        
        specs_y = y_base + 45
        
        # Scale in meters and feet
        scale_m = float(vehicle_data.get('scale_m', 0))
        scale_ft = scale_m * 3.28084
        
        scale_text = f"LENGTH: {scale_m:.1f}m / {scale_ft:.1f}ft"
        draw.text((margin_left, specs_y), scale_text, 
                  font=font_medium, fill=self.colors['text_primary'])
        
        # Country of origin (placeholder based on vehicle type)
        country = self._get_country_of_origin(vehicle_data.get('name', ''))
        country_text = f"ORIGIN: {country}"
        draw.text((margin_left, specs_y + 30), country_text, 
                  font=font_small, fill=self.colors['text_secondary'])
        
        # Estimated weight (placeholder based on scale)
        weight = self._estimate_weight(scale_m, vehicle_data.get('name', ''))
        weight_text = f"EST. WEIGHT: {weight}"
        draw.text((margin_left, specs_y + 55), weight_text, 
                  font=font_small, fill=self.colors['text_secondary'])
        
        # Right section: Order number badge
        order = vehicle_data.get('order', 1)
        badge_size = 50
        badge_x = width - badge_size - 30
        badge_y = y_base
        
        # Badge circle
        draw.ellipse(
            [badge_x, badge_y, badge_x + badge_size, badge_y + badge_size],
            fill=self.colors['progress_bg']
        )
        draw.ellipse(
            [badge_x + 3, badge_y + 3, badge_x + badge_size - 3, badge_y + badge_size - 3],
            outline=self.colors['text_accent'],
            width=2
        )
        
        # Badge number
        font_bold = self.get_font(24)
        text_bbox = draw.textbbox((0, 0), str(order), font=font_bold)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]
        text_x = badge_x + (badge_size - text_w) // 2
        text_y = badge_y + (badge_size - text_h) // 2
        
        draw.text((text_x, text_y), str(order), 
                  font=font_bold, fill=self.colors['text_accent'])
        
        return panel
    
    def _get_country_of_origin(self, vehicle_name):
        """Get country of origin based on vehicle name."""
        vehicle_name_lower = vehicle_name.lower()
        
        # US vehicles
        if any(v in vehicle_name_lower for v in ['sherman', 'abrams', 'humvee', 'willys', 
                                                   'apache', 'ac130', 'b2', 'ford']):
            return "USA"
        # Russian/Soviet vehicles
        elif any(v in vehicle_name_lower for v in ['t90', 'typhoon', 'ratte']):
            return "RUSSIA"
        # German vehicles
        elif 'panzer' in vehicle_name_lower or 'maus' in vehicle_name_lower:
            return "GERMANY"
        # Ukrainian aircraft
        elif 'an225' in vehicle_name_lower:
            return "UKRAINE"
        # Generic/unknown
        elif 'drone' in vehicle_name_lower or 'soldier' in vehicle_name_lower:
            return "INTERNATIONAL"
        else:
            return "CLASSIFIED"
    
    def _estimate_weight(self, scale_m, vehicle_name):
        """Estimate weight based on vehicle scale and type."""
        vehicle_name_lower = vehicle_name.lower()
        
        # Weight estimation logic (very approximate)
        if 'soldier' in vehicle_name_lower:
            return "80 kg / 176 lbs"
        elif 'drone' in vehicle_name_lower:
            return "2 kg / 4.4 lbs"
        elif 'jeep' in vehicle_name_lower or 'humvee' in vehicle_name_lower:
            return "2,500 kg / 5,511 lbs"
        elif 'sherman' in vehicle_name_lower:
            return "30,000 kg / 66,138 lbs"
        elif 't90' in vehicle_name_lower:
            return "46,000 kg / 101,412 lbs"
        elif 'abrams' in vehicle_name_lower:
            return "67,000 kg / 147,710 lbs"
        elif 'maus' in vehicle_name_lower:
            return "188,000 kg / 414,469 lbs"
        elif 'apache' in vehicle_name_lower:
            return "10,000 kg / 22,046 lbs"
        elif 'ac130' in vehicle_name_lower:
            return "70,000 kg / 154,323 lbs"
        elif 'ratte' in vehicle_name_lower:
            return "1,000,000 kg / 2,204,622 lbs"
        elif 'b2' in vehicle_name_lower:
            return "71,000 kg / 156,528 lbs"
        elif 'an225' in vehicle_name_lower:
            return "640,000 kg / 1,410,958 lbs"
        elif 'typhoon' in vehicle_name_lower:
            return "48,000,000 kg / 105,821,886 lbs"
        elif 'ford' in vehicle_name_lower or 'carrier' in vehicle_name_lower:
            return "100,000,000 kg / 220,462,262 lbs"
        else:
            # Rough estimate based on scale
            weight_kg = int(scale_m ** 3 * 100)  # Cube law approximation
            return f"{weight_kg:,} kg / {weight_kg * 2.20462:,.0f} lbs"
    
    def create_tactical_grid(self, width, height):
        """Create subtle tactical grid overlay."""
        grid = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(grid)
        
        grid_spacing = 100
        line_width = 1
        
        # Vertical lines
        for x in range(0, width, grid_spacing):
            alpha = 60 if x % (grid_spacing * 2) == 0 else 30
            draw.line([(x, 0), (x, height)], 
                     fill=(*self.colors['grid_lines'][:3], alpha), 
                     width=line_width)
        
        # Horizontal lines
        for y in range(0, height, grid_spacing):
            alpha = 60 if y % (grid_spacing * 2) == 0 else 30
            draw.line([(0, y), (width, y)], 
                     fill=(*self.colors['grid_lines'][:3], alpha), 
                     width=line_width)
        
        return grid
    
    def apply_color_correction(self, frame_image, contrast=1.15, saturation=0.95, vignette=True):
        """Apply cinematic color correction to frame."""
        # Convert to RGB if necessary
        if frame_image.mode != 'RGB':
            frame_image = frame_image.convert('RGB')
        
        # Apply contrast enhancement
        enhancer = ImageEnhance.Contrast(frame_image)
        frame_image = enhancer.enhance(contrast)
        
        # Apply saturation adjustment
        enhancer = ImageEnhance.Color(frame_image)
        frame_image = enhancer.enhance(saturation)
        
        # Apply vignette effect
        if vignette:
            width, height = frame_image.size
            vignette_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            vignette_draw = ImageDraw.Draw(vignette_layer)
            
            # Create radial gradient for vignette
            max_dist = min(width, height) / 2
            for r in range(int(max_dist), 0, -5):
                alpha = int(100 * (1 - r / max_dist) ** 2)
                vignette_draw.ellipse([
                    width // 2 - r, height // 2 - r,
                    width // 2 + r, height // 2 + r
                ], outline=(0, 0, 0, alpha), width=5)
            
            frame_image = Image.alpha_composite(frame_image.convert('RGBA'), vignette_layer)
        
        return frame_image
    
    def generate_frame_overlay(self, vehicle_data, current_index, total_objects, 
                                resolution=(1920, 1080)):
        """Generate complete overlay for a single frame."""
        width, height = resolution
        
        # Create base overlay layer
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        
        # Add tactical grid
        grid = self.create_tactical_grid(width, height)
        overlay.alpha_composite(grid)
        
        # Add progress bar (top)
        progress_bar = self.create_scale_progress_bar(
            width, current_index, total_objects, 
            vehicle_data.get('name', '')
        )
        overlay.paste(progress_bar, (0, 0), progress_bar)
        
        # Add info panel (bottom)
        info_panel = self.create_info_panel(vehicle_data, width, height)
        overlay.paste(info_panel, (0, height - info_panel.height), info_panel)
        
        return overlay
    
    def generate_all_overlays(self, csv_path, timestamps_path=None, output_format='png'):
        """Generate overlay frames for all vehicles in CSV."""
        print("\n" + "="*50)
        print("Generating Motion Graphics Overlays")
        print("="*50)
        
        # Download font
        self.download_font()
        
        # Load CSV data
        vehicles = []
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                vehicles.append(row)
        
        total_vehicles = len(vehicles)
        print(f"Processing {total_vehicles} vehicles...")
        
        # Load timestamps if available
        timestamps = {}
        if timestamps_path and os.path.exists(timestamps_path):
            with open(timestamps_path, 'r') as f:
                timestamps = json.load(f)
        
        generated_count = 0
        for i, vehicle in enumerate(vehicles):
            try:
                # Generate overlay
                overlay = self.generate_frame_overlay(
                    vehicle, i, total_vehicles, self.resolution
                )
                
                # Save overlay
                output_path = self.output_dir / f"overlay_{i:03d}.{output_format}"
                overlay.save(output_path)
                
                print(f"  ✓ Generated: overlay_{i:03d}.{output_format}")
                generated_count += 1
                
            except Exception as e:
                print(f"  ⚠ Error generating overlay {i}: {e}")
        
        print(f"\n✓ Generated {generated_count}/{total_vehicles} overlays")
        print(f"Output directory: {self.output_dir}")
        print("="*50 + "\n")
        
        return generated_count
    
    def apply_overlays_to_video(self, video_path, output_path, overlay_dir=None):
        """Apply generated overlays to video using FFmpeg."""
        import subprocess
        
        if overlay_dir is None:
            overlay_dir = self.output_dir
        
        # Check if FFmpeg is available
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠ FFmpeg not found. Overlay application skipped.")
            return False
        
        # Build FFmpeg command with overlay filter
        # This creates a complex filter that applies overlays based on timestamps
        
        print(f"Applying overlays to video: {video_path}")
        print(f"Output: {output_path}")
        
        # For now, apply static overlay (can be enhanced with per-frame overlays)
        latest_overlay = sorted(overlay_dir.glob("*.png"))[-1] if list(overlay_dir.glob("*.png")) else None
        
        if latest_overlay:
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', str(latest_overlay),
                '-filter_complex', '[0:v][1:v]overlay=0:0',
                '-c:a', 'copy',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '18',
                output_path
            ]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"✓ Overlays applied successfully: {output_path}")
                    return True
                else:
                    print(f"⚠ FFmpeg error: {result.stderr}")
                    return False
            except Exception as e:
                print(f"⚠ Error applying overlays: {e}")
                return False
        else:
            print("⚠ No overlay files found")
            return False


def main():
    """Main entry point for motion graphics generation."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate military HUD overlays for scale comparison videos')
    parser.add_argument('--csv', default='data/military_vehicles.csv',
                       help='Path to CSV file with vehicle data')
    parser.add_argument('--timestamps', default='data/timestamps.json',
                       help='Path to JSON file with frame timestamps')
    parser.add_argument('--output-dir', default='assets/graphics',
                       help='Output directory for overlays')
    parser.add_argument('--fonts-dir', default='assets/fonts',
                       help='Directory for fonts')
    parser.add_argument('--apply-to-video', default=None,
                       help='Apply overlays to video file')
    parser.add_argument('--output-video', default=None,
                       help='Output video path when applying overlays')
    
    args = parser.parse_args()
    
    # Get script directory for relative paths
    script_dir = Path(__file__).parent.parent
    csv_path = script_dir / args.csv if not os.path.isabs(args.csv) else Path(args.csv)
    timestamps_path = script_dir / args.timestamps if not os.path.isabs(args.timestamps) else Path(args.timestamps)
    
    # Initialize generator
    generator = MotionGraphicsGenerator(
        output_dir=args.output_dir if os.path.isabs(args.output_dir) else script_dir / args.output_dir,
        fonts_dir=args.fonts_dir if os.path.isabs(args.fonts_dir) else script_dir / args.fonts_dir
    )
    
    # Set resolution based on typical render settings
    generator.resolution = (1920, 1080)
    
    # Generate overlays
    generator.generate_all_overlays(str(csv_path), str(timestamps_path))
    
    # Apply to video if requested
    if args.apply_to_video and args.output_video:
        video_path = Path(args.apply_to_video) if os.path.isabs(args.apply_to_video) else script_dir / args.apply_to_video
        output_path = Path(args.output_video) if os.path.isabs(args.output_video) else script_dir / args.output_video
        generator.apply_overlays_to_video(str(video_path), str(output_path))


if __name__ == "__main__":
    main()
