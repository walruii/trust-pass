import os
import sys
import json

# Ensure backend package is importable
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.ocr import extract_passport_data


def mime_from_path(path: str) -> str:
    lower = path.lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    raise SystemExit("Unsupported image type; provide .png or .jpg file")


def main():
    if len(sys.argv) != 2:
        print("Usage: python test_extract_from_file.py path/to/passport_image.jpg")
        raise SystemExit(2)

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"File not found: {path}")
        raise SystemExit(2)

    with open(path, "rb") as f:
        image_bytes = f.read()

    mime = mime_from_path(path)
    result = extract_passport_data(image_bytes, mime)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
