import os
import json
import sys

# Ensure backend package is importable
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.ocr import get_ocr_runtime_status


def main():
    status = get_ocr_runtime_status()
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
