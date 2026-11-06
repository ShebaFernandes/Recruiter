"""Regenerate lossless WebP artwork and responsive copies; retain all source images."""
import json
from pathlib import Path
from PIL import Image, ImageChops

root = Path(__file__).resolve().parents[1]
sources = [
    'media/section10-closing-mountain-lush.png',
    'media/hiring-enquiry-landscape-v1.png',
    'media/growth-stages/founding-teams-hills.png',
    'media/growth-stages/leadership-lake.png',
]
out = root / 'src/assets/optimized'
out.mkdir(parents=True, exist_ok=True)
report = []
for name in sources:
    source = root / 'public' / name
    image = Image.open(source).convert('RGB')
    target = out / (source.stem + '.webp')
    color_profile = {'icc_profile': image.info['icc_profile']} if image.info.get('icc_profile') else {}
    image.save(target, 'WEBP', lossless=True, method=6, **color_profile)
    assert ImageChops.difference(image, Image.open(target).convert('RGB')).getbbox() is None
    mobile = image.copy()
    mobile.thumbnail((960, 9600), Image.Resampling.LANCZOS)
    small = out / (source.stem + '-960.webp') if image.width > 960 else target
    if small != target:
        mobile.save(small, 'WEBP', lossless=True, method=6, **color_profile)
    report.append(dict(source=name, width=image.width, height=image.height,
                       original_bytes=source.stat().st_size, optimized_bytes=target.stat().st_size,
                       mobile_bytes=small.stat().st_size, pixel_identical=True))
(root.parent / 'reports/performance/images.json').write_text(json.dumps(report, indent=2))
