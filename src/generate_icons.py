#!/usr/bin/env python3
"""
generate_icons.py – Gera ícones PNG simples para o PWA.
Executar uma vez manualmente ou via CI se necessário.
Requer: Pillow (pip install Pillow)

Uso: python3 generate_icons.py
"""
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
    USE_PILLOW = True
except ImportError:
    USE_PILLOW = False


def create_icon_pillow(size: int, path: str) -> None:
    """Cria ícone com Pillow (qualidade superior)."""
    img = Image.new("RGBA", (size, size), (15, 23, 42, 255))  # --bg: #0f172a
    draw = ImageDraw.Draw(img)

    # Fundo arredondado
    margin = size // 8
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=size // 6,
        fill=(30, 41, 59, 255),  # --bg-card: #1e293b
    )

    # Símbolo "📰" simplificado: retângulo claro (manchete) + linhas
    inner_x = margin * 2
    inner_y = margin * 2
    inner_w = size - margin * 4
    line_h = max(2, size // 32)

    # Manchete
    draw.rectangle(
        [inner_x, inner_y, inner_x + inner_w, inner_y + size // 6],
        fill=(56, 189, 248, 255),  # --accent: #38bdf8
    )

    # Linhas de texto
    y = inner_y + size // 6 + margin // 2
    for _ in range(5):
        if y + line_h < size - margin * 2:
            draw.rectangle([inner_x, y, inner_x + inner_w, y + line_h], fill=(148, 163, 184, 200))
            y += line_h + max(2, size // 20)

    img.save(path, "PNG")
    print(f"  ✓ {path} ({size}×{size})")


def create_icon_basic(size: int, path: str) -> None:
    """Cria PNG básico sem dependências externas."""
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
                # faixa de destaque no topo
                if y < margin + size // 6:
                    r, g, b = accent
                # linhas de texto
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
    print(f"  ✓ {path} ({size}×{size}) [basic]")


if __name__ == '__main__':
    out = os.path.join(os.path.dirname(__file__), '..', 'docs', 'icons')
    os.makedirs(out, exist_ok=True)

    for size in [192, 512]:
        dest = os.path.join(out, f'icon-{size}.png')
        if USE_PILLOW:
            create_icon_pillow(size, dest)
        else:
            create_icon_basic(size, dest)

    print("Ícones gerados com sucesso!")
