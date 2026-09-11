from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
CROPS = ASSETS / "manual-crops"


# These captures contain a desktop page in the upper-left of a larger canvas.
# Keep the full rendered page and remove only the unused canvas area.
CROP_BOXES = {
    "manual-worklogs.png": (0, 0, 736, 416),
    "manual-approvals.png": (0, 0, 736, 416),
}


def main():
    CROPS.mkdir(parents=True, exist_ok=True)
    for name, box in CROP_BOXES.items():
        source = ASSETS / name
        target = CROPS / name
        with Image.open(source) as image:
            image.crop(box).save(target, format="PNG", optimize=True)
        print(f"wrote {target} {box}")


if __name__ == "__main__":
    main()
