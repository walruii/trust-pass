"""
Module 3: Tampering Detection (core AI/forensics innovation).

Three independent, well-established digital-forensics techniques, each
producing an evidence flag with a localized region when possible:

1. Error Level Analysis (ELA) - re-saves the image at a known JPEG
   quality and diffs it against the original. Regions that were pasted
   in from a different source/compression history "light up" because
   they compress differently than the rest of the (already-compressed)
   image. Classic signal for photo-replacement and text edits.

2. Metadata / EXIF forensics - looks for editing-software signatures
   (Photoshop, GIMP, Snapseed...), missing capture metadata, or
   inconsistent modification-vs-creation timestamps.

3. Copy-move forgery detection - uses ORB keypoint matching to find
   regions of the image that are near-duplicates of another region
   elsewhere in the same image (a common way to hide/duplicate a stamp
   or cover a digit).
"""
import io
import cv2
import numpy as np
from PIL import Image, ExifTags

EDITING_SOFTWARE_SIGNATURES = [
    "photoshop", "gimp", "snapseed", "picsart", "lightroom",
    "paint.net", "pixlr", "canva", "affinity",
]


def error_level_analysis(image_bgr: np.ndarray, quality: int = 90):
    ok, encoded = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        return {"mean_error": 0.0, "max_error": 0.0, "suspicious_regions": [], "error": "encode_failed"}
    resaved = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if resaved.shape != image_bgr.shape:
        resaved = cv2.resize(resaved, (image_bgr.shape[1], image_bgr.shape[0]))

    diff = cv2.absdiff(image_bgr, resaved).astype(np.float32)
    diff_gray = cv2.cvtColor(diff.astype(np.uint8), cv2.COLOR_BGR2GRAY)
    diff_gray = cv2.normalize(diff_gray, None, 0, 255, cv2.NORM_MINMAX)

    mean_error = float(np.mean(diff_gray))
    max_error = float(np.max(diff_gray))

    # Threshold + contour the hottest ELA regions as candidate tamper zones
    _, thresh = cv2.threshold(diff_gray, max(180, int(mean_error * 4)), 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = diff_gray.shape
    min_area = 0.002 * h * w  # ignore tiny noise specks
    regions = []
    for c in contours:
        area = cv2.contourArea(c)
        if area >= min_area:
            x, y, bw, bh = cv2.boundingRect(c)
            regions.append({"x": x, "y": y, "w": bw, "h": bh, "area": float(area)})
    regions.sort(key=lambda r: -r["area"])

    return {
        "mean_error": round(mean_error, 2),
        "max_error": round(max_error, 2),
        "suspicious_regions": regions[:5],
    }


def metadata_forensics(image_path: str):
    flags = []
    info = {}
    try:
        img = Image.open(image_path)
        exif_raw = img._getexif() if hasattr(img, "_getexif") else None
        if not exif_raw:
            flags.append("No EXIF metadata present (common after re-saving/editing, or a scan/screenshot).")
        else:
            exif = {ExifTags.TAGS.get(k, k): v for k, v in exif_raw.items()}
            software = str(exif.get("Software", "")).lower()
            info["software_tag"] = exif.get("Software")
            info["datetime_original"] = exif.get("DateTimeOriginal")
            info["datetime_modified"] = exif.get("DateTime")
            if software:
                for sig in EDITING_SOFTWARE_SIGNATURES:
                    if sig in software:
                        flags.append(f"EXIF 'Software' tag indicates image editing tool: '{exif.get('Software')}'.")
                        break
            dto, dtm = exif.get("DateTimeOriginal"), exif.get("DateTime")
            if dto and dtm and dto != dtm:
                flags.append(f"Capture time ({dto}) differs from last-modified time ({dtm}) -- image was re-saved after capture.")
    except Exception as e:
        flags.append(f"Could not read metadata: {e}")
    return {"flags": flags, "info": info}


def copy_move_detection(image_bgr: np.ndarray, min_matches: int = 40, max_hamming_distance: int = 24):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(nfeatures=2000)
    kp, des = orb.detectAndCompute(gray, None)
    if des is None or len(kp) < 10:
        return {"duplicated_regions_found": False, "match_count": 0}

    diag = float(np.hypot(*gray.shape))
    min_self_distance = max(25, 0.03 * diag)  # scale with image size; ignore trivial neighbor keypoints

    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    matches = bf.knnMatch(des, des, k=3)  # k=3 because best match is always itself

    good_pairs = []
    for m in matches:
        for cand in m[1:]:  # skip index 0 (self-match)
            if cand.distance > max_hamming_distance:
                continue  # require a genuinely strong descriptor match, not a loose one
            pt1 = np.array(kp[cand.queryIdx].pt)
            pt2 = np.array(kp[cand.trainIdx].pt)
            if np.linalg.norm(pt1 - pt2) > min_self_distance:
                good_pairs.append((cand.queryIdx, cand.trainIdx, cand.distance))

    match_count = len(good_pairs)
    if match_count < min_matches:
        return {"duplicated_regions_found": False, "match_count": match_count, "inlier_count": 0}

    # Real copy-move forgery produces matches that share a consistent geometric
    # transform (the pasted patch was translated/rotated/scaled as a rigid block).
    # Spurious matches on repetitive textures (grass, flat backgrounds, fine
    # patterns) scatter randomly instead. RANSAC-fit an affine transform and
    # only trust the match count if enough pairs agree with ONE transform.
    src_pts = np.float32([kp[i].pt for i, _, _ in good_pairs]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp[j].pt for _, j, _ in good_pairs]).reshape(-1, 1, 2)
    inlier_count = 0
    try:
        _, inliers = cv2.estimateAffinePartial2D(src_pts, dst_pts, method=cv2.RANSAC, ransacReprojThreshold=3.0)
        if inliers is not None:
            inlier_count = int(inliers.sum())
    except cv2.error:
        inlier_count = 0

    return {
        "duplicated_regions_found": inlier_count >= min_matches,
        "match_count": match_count,
        "inlier_count": inlier_count,
    }


def run_all(image_bgr: np.ndarray, image_path: str):
    return {
        "error_level_analysis": error_level_analysis(image_bgr),
        "metadata": metadata_forensics(image_path),
        "copy_move": copy_move_detection(image_bgr),
    }
