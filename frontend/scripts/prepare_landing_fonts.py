"""Keep exact Newsreader glyphs/optical sizing; pin only CSS-declared weights.

Run with fonttools[woff]. Original fonts and their OFL license remain untouched.
"""

from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

root = Path(__file__).resolve().parents[1] / "src/assets/fonts"
for weight in (500, 600):
    source = TTFont(root / "c2789104223d80ae.woff2")
    instance = instantiateVariableFont(source, {"wght": weight}, inplace=False)
    instance.flavor = "woff2"
    target = root / f"newsreader-latin-{weight}.woff2"
    instance.save(target)
    encoded = TTFont(target)
    assert encoded.getBestCmap() == source.getBestCmap()
    assert encoded["hmtx"].metrics == instance["hmtx"].metrics
    assert [axis.axisTag for axis in encoded["fvar"].axes] == ["opsz"]
    print(weight, target.stat().st_size)
