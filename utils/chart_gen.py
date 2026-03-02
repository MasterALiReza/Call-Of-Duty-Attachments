import os
import io
import logging
from typing import List, Dict, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger('utils.chart_gen')

class ChartGenerator:
    """
    Utility to generate simple visual charts using Pillow.
    """
    def __init__(self, width: int = 800, height: int = 400, theme: str = 'dark'):
        self.width = width
        self.height = height
        self.theme = theme
        
        # Colors based on theme
        if theme == 'dark':
            self.bg_color = (25, 25, 35)      # Dark blueish gray
            self.text_color = (230, 230, 240) # Off-white
            self.grid_color = (60, 60, 75)    # Muted gray
            self.bar_color = (70, 130, 255)   # CoDM Blue
            self.accent_color = (255, 170, 0) # Gold/Orange
        else:
            self.bg_color = (255, 255, 255)
            self.text_color = (40, 40, 50)
            self.grid_color = (220, 220, 230)
            self.bar_color = (40, 100, 220)
            self.accent_color = (200, 140, 0)

    def generate_bar_chart(self, data: List[Tuple[str, float]], title: str = "") -> io.BytesIO:
        """
        Generates a bar chart image and returns it as a BytesIO object.
        """
        img = Image.new('RGB', (self.width, self.height), color=self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Margins
        margin_l, margin_r = 80, 40
        margin_t, margin_b = 60, 60
        
        chart_w = self.width - margin_l - margin_r
        chart_h = self.height - margin_t - margin_b
        
        if not data:
            return self._empty_chart(title)

        max_val = max(d[1] for d in data) if data else 1
        # Round up max_val for better scale
        scale_max = ((int(max_val) // 10) + 1) * 10 if max_val > 10 else 10
        
        # Draw Title
        draw.text((self.width // 2, 30), title, fill=self.text_color, anchor="mm")
        
        # Draw Axis
        draw.line([(margin_l, margin_t), (margin_l, self.height - margin_b)], fill=self.grid_color, width=2)
        draw.line([(margin_l, self.height - margin_b), (self.width - margin_r, self.height - margin_b)], fill=self.grid_color, width=2)
        
        num_bars = len(data)
        bar_gap = 10
        bar_w = (chart_w // num_bars) - bar_gap
        
        for i, (label, value) in enumerate(data):
            # Calculate coordinates
            norm_val = value / scale_max
            h = int(chart_h * norm_val)
            
            x0 = margin_l + i * (bar_w + bar_gap) + bar_gap // 2
            y0 = self.height - margin_b - h
            x1 = x0 + bar_w
            y1 = self.height - margin_b
            
            # Draw bar
            draw.rectangle([x0, y0, x1, y1], fill=self.bar_color)
            
            # Draw value label
            draw.text((x0 + bar_w // 2, y0 - 15), str(int(value)), fill=self.text_color, anchor="mm")
            
            # Draw X label (truncated if needed)
            display_label = label[:10] + ".." if len(label) > 12 else label
            draw.text((x0 + bar_w // 2, self.height - margin_b + 20), display_label, fill=self.text_color, anchor="mm")

        # Buffer for output
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

    def _empty_chart(self, title: str) -> io.BytesIO:
        img = Image.new('RGB', (self.width, self.height), color=self.bg_color)
        draw = ImageDraw.Draw(img)
        draw.text((self.width // 2, self.height // 2), f"No data for: {title}", fill=self.text_color, anchor="mm")
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

# Quick usage
# chart = ChartGenerator()
# buf = chart.generate_bar_chart([("Mon", 10), ("Tue", 25), ("Wed", 15)], "Weekly Growth")
