"""Heuristic plate localization plus CPU Tesseract OCR.

This is not a trained license plate detector; benchmark on real footage before use.
"""
import re


def normalize_plate(raw):
    value = re.sub("[^A-Z0-9]", "", raw.upper())
    return value if 4 <= len(value) <= 9 else None


def read_plate(frame, box, minimum_confidence=55):
    import cv2
    import pytesseract
    from pytesseract import Output

    h, w = frame.shape[:2]
    x1, y1, x2, y2 = [int(v) for v in box]
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return None
    roi = frame[y1:y2, x1:x2]
    rh, rw = roi.shape[:2]
    if rw < 60 or rh < 25:
        return None
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    contours = cv2.findContours(
        cv2.Canny(cv2.bilateralFilter(gray, 7, 45, 45), 60, 150),
        cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[-2]
    candidate_boxes = []
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:80]:
        x, y, bw, bh = cv2.boundingRect(contour)
        if 2 <= bw / max(1, bh) <= 6.5 and 35 <= bw <= rw * .85 and bh >= 10:
            candidate_boxes.append((x, y, bw, bh))
    candidate_boxes.append((int(rw * .2), int(rh * .35),
                            int(rw * .6), int(rh * .5)))
    best = None
    for x, y, bw, bh in candidate_boxes[:7]:
        crop = gray[y:y + bh, x:x + bw]
        if crop.size == 0:
            continue
        enlarged = cv2.resize(crop, None, fx=2, fy=2,
                              interpolation=cv2.INTER_CUBIC)
        for processed in (enlarged, cv2.adaptiveThreshold(
                enlarged, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 25, 8)):
            result = pytesseract.image_to_data(
                processed, output_type=Output.DICT,
                config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
            plate = normalize_plate("".join(result["text"]))
            confidences = [float(c) for c in result["conf"] if float(c) >= 0]
            quality = sum(confidences) / len(confidences) if confidences else -1
            if plate and quality >= minimum_confidence:
                if best is None or quality > best[1]:
                    best = (plate, quality)
    return best
