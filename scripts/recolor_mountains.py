"""Create deterministic deep-navy derivatives; never modify source artwork.

Run with the existing backend environment: .venv/bin/python scripts/recolor_mountains.py
Pillow only. Original geometry and alpha are retained. Mountains use deliberately
deeper navy midtones; sky and mist remain pale blue-white for readable foreground text.
"""

import hashlib
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "hero"
SOURCE = ROOT / "mountain-v1"
TARGET = ROOT / "mountain-navy-v1"
LAYERS = (
    "sky", "mountains-distant", "mountains-middle", "mountains-foreground",
    "clouds-back", "clouds-front",
)


def grade(value, stops):
    for (low, start), (high, end) in zip(stops, stops[1:], strict=False):
        if value <= high:
            blend = (value - low) / (high - low)
            return tuple(round(a + (b - a) * blend) for a, b in zip(start, end, strict=True))
    return stops[-1][1]


def main():
    TARGET.mkdir(exist_ok=True)
    for name in LAYERS:
        source = SOURCE / f"{name}.webp"
        original_hash = hashlib.sha256(source.read_bytes()).digest()
        image = Image.open(source).convert("RGBA")
        alpha = image.getchannel("A")
        luminance = image.convert("RGB").convert("L", (0.2126, 0.7152, 0.0722, 0))
        # A tonal curve rather than a flat overlay keeps ridge texture and mist.
        stops = (
            [(0, (6, 23, 47)), (128, (11, 40, 80)), (180, (22, 59, 101)),
             (215, (91, 136, 179)), (240, (200, 225, 245)), (255, (255, 255, 255))]
            if name.startswith("mountains") else
            [(0, (100, 145, 190)), (200, (215, 234, 250)), (255, (255, 255, 255))]
        )
        palette = [grade(value, stops) for value in range(256)]
        channels = [luminance.point([color[channel] for color in palette])
                    for channel in range(3)]
        result = Image.merge("RGBA", (*channels, alpha))
        destination = TARGET / source.name
        result.save(destination, format="WEBP", lossless=True, method=6, exact=True)
        decoded = Image.open(destination).convert("RGBA")
        assert decoded.size == image.size
        assert ImageChops.difference(alpha, decoded.getchannel("A")).getbbox() is None
        assert hashlib.sha256(source.read_bytes()).digest() == original_hash
        # Every nontransparent output pixel is neutral/cool blue, never magenta.
        assert all(r <= g <= b for r, g, b, a in decoded.get_flattened_data() if a)
        output_luma = decoded.convert("RGB").convert("L", (0.2126, 0.7152, 0.0722, 0))
        delta = ImageStat.Stat(ImageChops.difference(luminance, output_luma), alpha).mean[0]
        print(f"{name}: {decoded.size}, alpha identical, luma delta {delta:.3f}/255, "
              f"{destination.stat().st_size // 1024} KiB; source unchanged")


if __name__ == "__main__":
    main()
