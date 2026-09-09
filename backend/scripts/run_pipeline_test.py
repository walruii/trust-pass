import sys
import os
import json
from dataclasses import dataclass

# Ensure backend package is importable
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.pipeline import run_placeholder_stages


@dataclass
class FakeImage:
    image_type: str
    mime_type: str
    image_bytes: bytes


@dataclass
class FakeApplication:
    images: list


def make_blank_png_bytes() -> bytes:
    # Minimal valid 1x1 PNG
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01\x0d\n\x02\x1d\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def main():
    image_bytes = None
    if len(sys.argv) >= 2 and sys.argv[1] != "--sample":
        path = sys.argv[1]
        if not os.path.exists(path):
            print(f"File not found: {path}")
            raise SystemExit(2)
        with open(path, "rb") as f:
            image_bytes = f.read()
        mime = "image/jpeg" if path.lower().endswith((".jpg", ".jpeg")) else "image/png"
    else:
        image_bytes = make_blank_png_bytes()
        mime = "image/png"

    app = FakeApplication(images=[FakeImage(image_type="passport", mime_type=mime, image_bytes=image_bytes)])
    result = run_placeholder_stages(app)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
