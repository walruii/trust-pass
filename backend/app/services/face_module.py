"""
Module 4: Face Verification.

Uses OpenCV's DNN module (cv2.dnn) with a small SSD-based face detector
(ResNet-10 backbone, Caffe weights) instead of the old Haar-cascade
CascadeClassifier. Two reasons:

  1. Accuracy: this DNN detector is meaningfully more robust than Haar
     cascades to pose, lighting, and partial occlusion.
  2. Portability: cv2.dnn lives in OpenCV's core module in BOTH OpenCV
     4.x and 5.x. The old Haar/HOG CascadeClassifier was moved out of
     core into opencv_contrib in OpenCV 5.0, which is what breaks on
     newer installs. Using cv2.dnn instead means this code runs
     unmodified regardless of which OpenCV major version is installed.

The model files (deploy.prototxt + the .caffemodel weights) are bundled
in document_analyzer/data/ so nothing needs to be downloaded at runtime.

PROTOTYPE-GRADE NOTE: face *matching* below still uses a histogram +
pixel-similarity comparison, not a real face-recognition embedding
model. That's fine for demonstrating the pipeline end-to-end but is
NOT production-accurate. For a real deployment, swap `compare_faces()`
for embeddings from an ArcFace/FaceNet/SFace model and compare with
cosine similarity -- detection (this module) and matching are
independent steps, so only the matching half needs to change.
"""
import os
import cv2
import numpy as np

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_PROTOTXT_PATH = os.path.join(_DATA_DIR, "deploy.prototxt")
_MODEL_PATH = os.path.join(_DATA_DIR, "res10_300x300_ssd_iter_140000_fp16.caffemodel")

_net = None


def _get_net():
    global _net
    if _net is None:
        if not (os.path.exists(_PROTOTXT_PATH) and os.path.exists(_MODEL_PATH)):
            raise RuntimeError(
                f"Face detector model files not found in {_DATA_DIR}. "
                "Make sure document_analyzer/data/ (deploy.prototxt and the .caffemodel) "
                "was included when you copied the project."
            )
        # _net = cv2.dnn.readNetFromCaffe(_PROTOTXT_PATH, _MODEL_PATH)
        _net = cv2.dnn.readNet(_PROTOTXT_PATH, _MODEL_PATH)
    return _net


def detect_largest_face(image_bgr: np.ndarray, conf_threshold: float = 0.5):
    net = _get_net()
    h, w = image_bgr.shape[:2]
    blob = cv2.dnn.blobFromImage(
        cv2.resize(image_bgr, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0)
    )
    net.setInput(blob)
    detections = net.forward()

    best = None
    best_area = 0
    for i in range(detections.shape[2]):
        confidence = float(detections[0, 0, i, 2])
        if confidence < conf_threshold:
            continue
        box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
        x1, y1, x2, y2 = box.astype(int)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        area = max(0, x2 - x1) * max(0, y2 - y1)
        if area > best_area:
            best_area = area
            best = (x1, y1, x2, y2)

    if best is None:
        return None
    x1, y1, x2, y2 = best
    if x2 <= x1 or y2 <= y1:
        return None
    return image_bgr[y1:y2, x1:x2]


def _face_signature(face_bgr: np.ndarray):
    face = cv2.resize(face_bgr, (128, 128))
    gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    # Flatten the face to a single vector and normalize it for cosine similarity.
    vector = gray.astype(np.float32).reshape(-1)
    norm = np.linalg.norm(vector)
    if norm == 0:
        return gray, np.zeros_like(vector)
    return gray, vector / norm


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    if vec_a.size == 0 or vec_b.size == 0:
        return 0.0
    return float(np.clip(np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b)), -1.0, 1.0))


def compare_faces(doc_image_bgr: np.ndarray, selfie_image_bgr: np.ndarray):
    doc_face = detect_largest_face(doc_image_bgr)
    selfie_face = detect_largest_face(selfie_image_bgr)

    if doc_face is None or selfie_face is None:
        return {
            "doc_face_found": doc_face is not None,
            "selfie_face_found": selfie_face is not None,
            "similarity": None,
            "match": None,
            "note": "Could not detect a face in one or both images.",
        }

    gray1, vec1 = _face_signature(doc_face)
    gray2, vec2 = _face_signature(selfie_face)

    cosine_score = cosine_similarity(vec1, vec2)
    hist = cv2.calcHist([gray1], [0], None, [64], [0, 256])
    hist2 = cv2.calcHist([gray2], [0], None, [64], [0, 256])
    cv2.normalize(hist, hist)
    cv2.normalize(hist2, hist2)
    hist_score = cv2.compareHist(hist, hist2, cv2.HISTCMP_CORREL)

    # Combine cosine similarity with a mild histogram correlation score.
    similarity = float(np.clip(0.7 * cosine_score + 0.3 * ((hist_score + 1) / 2), 0.0, 1.0))

    return {
        "doc_face_found": True,
        "selfie_face_found": True,
        "similarity": round(similarity, 3),
        "cosine_similarity": round(float(cosine_score), 3),
        "match": similarity >= 0.55,
        "method": "cosine_similarity_on_normalized_face_vector",
        "note": "Face verification uses cosine similarity between the passport face crop and the live selfie feature vectors.",
    }
