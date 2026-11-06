"""Generate responsive copies of the existing artwork; never replace source artwork."""

import argparse
import base64
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src/assets/landing"
SOURCES = {
    "founding": "media/growth-stages/founding-teams-hills.png",
    "leadership": "media/growth-stages/leadership-lake.png",
    "closing": "media/section10-closing-mountain-lush.png",
    "evidence": "media/hiring-enquiry-landscape-v1.png",
    "ambition": "media/ambition-hires-mountain.jpg",
    **{
        plate.replace("-", "_"): f"hero/mountain-v1/{plate}.webp"
        for plate in (
            "sky",
            "mountains-distant",
            "mountains-middle",
            "clouds-back",
            "mountains-foreground",
            "clouds-front",
        )
    },
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report", type=Path, default=Path("/tmp/enter-webperf-20261104/images.json")
    )
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    imports, objects, report = [], [], []
    for name, relative in SOURCES.items():
        source = ROOT / "public" / relative
        image = Image.open(source)
        # Match the existing RGB lossless landscape conversions. Hero alpha is retained.
        image = image.convert(
            "RGBA" if relative.startswith("hero/") and "A" in image.getbands() else "RGB"
        )
        profile = (
            {"icc_profile": image.info["icc_profile"]} if image.info.get("icc_profile") else {}
        )
        widths = sorted(
            {width for width in (320, 640, 960, 1440, image.width) if width <= image.width}
        )
        encodings = {}
        sizes = []
        for fmt, quality in (("webp", 88), ("avif", 70)):
            candidates = []
            for width in widths:
                resized = image.resize(
                    (width, round(image.height * width / image.width)), Image.Resampling.LANCZOS
                )
                target = OUT / f"{name}-{width}.{fmt}"
                options = {"quality": quality, **profile}
                options.update({"method": 6} if fmt == "webp" else {"speed": 6})
                resized.save(target, fmt.upper(), **options)
                identifier = f"{name}_{fmt}_{width}"
                imports.append(f"import {identifier} from './{target.name}'")
                candidates.append((identifier, width))
                error = ImageStat.Stat(
                    ImageChops.difference(resized.convert("RGB"), Image.open(target).convert("RGB"))
                ).rms
                sizes.append(
                    {
                        "format": fmt,
                        "width": width,
                        "height": resized.height,
                        "bytes": target.stat().st_size,
                        "rgb_rmse": round(sum(error) / 3, 3),
                    }
                )
            encodings[fmt] = candidates
        thumbnail = image.copy()
        thumbnail.thumbnail((64, 64))
        from io import BytesIO

        buffer = BytesIO()
        thumbnail.save(buffer, "WEBP", quality=40)
        preview = "data:image/webp;base64," + base64.b64encode(buffer.getvalue()).decode()
        fields = [
            f"width: {image.width}",
            f"height: {image.height}",
            f"original: {json.dumps('/' + relative)}",
            f"preview: {json.dumps(preview)}",
        ]
        for fmt, candidates in encodings.items():
            srcset = ", ".join(
                "${" + identifier + "} " + str(width) + "w" for identifier, width in candidates
            )
            fields.extend([f"{fmt}: {candidates[-1][0]}", f"{fmt}SrcSet: `{srcset}`"])
        objects.append(f"  {name}: {{" + ", ".join(fields) + "}")
        report.append(
            {
                "name": name,
                "source": relative,
                "width": image.width,
                "height": image.height,
                "original_bytes": source.stat().st_size,
                "variants": sizes,
            }
        )
    (OUT / "artwork.ts").write_text(
        "\n".join(imports)
        + "\n\nexport const artwork = {\n"
        + ",\n".join(objects)
        + "\n} as const\n"
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Generated {len(imports)} responsive assets from {len(SOURCES)} unchanged originals.")


if __name__ == "__main__":
    main()
