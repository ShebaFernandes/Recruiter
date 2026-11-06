"""Subset the existing landing typeface; preserve glyph outlines and optical sizing."""
from pathlib import Path

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

root = Path(__file__).resolve().parents[1] / "src/assets/fonts"
for weight in (500, 600):
    original = TTFont(root / f"newsreader-latin-{weight}.woff2")
    font = TTFont(root / f"newsreader-latin-{weight}.woff2")
    options = Options()
    options.layout_features = ["*"]
    options.recalc_timestamp = False
    subset = Subsetter(options=options)
    subset.populate(unicodes=list(range(32, 127)) + list(range(0x2000, 0x2070)) + [0xA0, 0x2192])
    subset.subset(font)
    for size in (14, 52, 72):
        before = original.getGlyphSet(location={"opsz": size})
        after = font.getGlyphSet(location={"opsz": size})
        for point, glyph in font.getBestCmap().items():
            a, b = DecomposingRecordingPen(before), DecomposingRecordingPen(after)
            before[original.getBestCmap()[point]].draw(a)
            after[glyph].draw(b)
            assert a.value == b.value, f"Changed outline: {point} at {size}"
    font.flavor = "woff2"
    target = root / f"newsreader-landing-{weight}.woff2"
    font.save(target)
    print(target.name, target.stat().st_size)
