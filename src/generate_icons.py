#!/usr/bin/env python3
"""
generate_icons.py – Generates simple PNG icons for the PWA.
Run manually or via CI when icons need updating.
Optional: Pillow (pip install Pillow)
"""
import os
import sys

try:
    from PIL import Image, ImageDraw
    USE_PILLOW = True
except ImportError:
    USE_PILLOW = False


def create_icon_pillow(size: int, path: str) -> None:
    """Creates a high-quality icon using Pillow."""
    img = Image.new("RGBA", (size, size), (15, 23, 42, 255))  # --bg: #0f172a
    draw = ImageDraw.Draw(img)

    margin = size // 8
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=size // 6,
        fill=(30, 41, 59, 255),  # --bg-card: #1e293b
    )

    inner_x = margin * 2
    inner_y = margin * 2
    inner_w = size - margin * 4
    line_h = max(2, size // 32)

    # Accent header bar
    draw.rectangle(
        [inner_x, inner_y, inner_x + inner_w, inner_y + size // 6],
        fill=(56, 189, 248, 255),  # --accent: #38bdf8
    )

    # Content lines
    y = inner_y + size // 6 + margin // 2
    for _ in range(5):
        if y + line_h < size - margin * 2:
            draw.rectangle([inner_x, y, inner_x + inner_w, y + line_h], fill=(148, 163, 184, 200))
            y += line_h + max(2, size // 20)

    img.save(path, "PNG")
    print(f"  ✓ {path} ({size}x{size})")


def create_icon_basic(size: int, path: str) -> None:
    """Creates a basic PNG icon using stdlib only."""
    import struct, zlib

    width = height = size
    bg = (15, 23, 42)
    accent = (56, 189, 248)

    raw = b''
    for y in range(height):
        raw += b'\x00'
        for x in range(width):
            r, g, b = bg
            margin = size // 8
            if margin <= x <= size - margin and margin <= y <= size - margin:
                r, g, b = (30, 41, 59)
                if y < margin + size // 6:
                    r, g, b = accent
                elif (y - margin) % (size // 16) < size // 32:
                    r, g, b = (94, 113, 130)
            raw += bytes([r, g, b, 255])

    def chunk(name, data):
        c = name + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)

    ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', ihdr)
    png += chunk(b'IDAT', zlib.compress(raw))
    png += chunk(b'IEND', b'')

    with open(path, 'wb') as f:
        f.write(png)
    print(f"  ✓ {path} ({size}x{size}) [basic]")


if __name__ == '__main__':
    out = os.path.join(os.path.dirname(__file__), '..', 'docs', 'icons')
    os.makedirs(out, exist_ok=True)

    for size in [192, 512]:
        dest = os.path.join(out, f'icon-{size}.png')
        if USE_PILLOW:
            create_icon_pillow(size, dest)
        else:
            create_icon_basic(size, dest)

    print("Icons generated successfully!")
