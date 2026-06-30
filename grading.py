import cv2
import json
import numpy as np
from utils import print_image
from scan_processing import get_bubble_coordinates

ANSWER_FIELDS = {"1-25", "26-50", "51-75"}


# ── Template index ────────────────────────────────────────────────

def build_bubble_index(template: dict) -> list[dict]:
    """
    Returns a flat list mirroring the order of get_bubble_coordinates().
    index[i]  ↔  bubble_coordinates[i]
    """

    index = []
    for field in template["fields"]:
        bw = field["bubble"]["width"]
        bh = field["bubble"]["height"]
        for entry in field["entries"]:
            for bubble in entry["bubbles"]:
                index.append({
                    "field":    field["name"],
                    "question": entry["question"],
                    "value":    bubble["value"],
                    "w":        bw,
                    "h":        bh,
                })
    return index


# ── Fill sampling ─────────────────────────────────────────────────

def sample_fill(cleaned: np.ndarray, cx: float, cy: float,
                bw: int, bh: int) -> float:
    """
    Counts white pixels (filled regions) in the bubble's bounding box
    on the already-thresholded `cleaned` image.
    Returns a ratio 0.0 (blank) → 1.0 (fully filled).
    """
    cx, cy = int(round(cx)), int(round(cy))
    hw, hh = bw // 2, bh // 2

    x1 = max(0, cx - hw);  x2 = min(cleaned.shape[1], cx + hw)
    y1 = max(0, cy - hh);  y2 = min(cleaned.shape[0], cy + hh)

    roi = cleaned[y1:y2, x1:x2]
    if roi.size == 0:
        return 0.0
    return float(np.count_nonzero(roi)) / roi.size

# Generate answer key
def generate_answer_key(img, bubble_coordinates, template, fill_threshold=0.55, final_w=2480, final_h=3508):
    # ── 1. Preprocess (your existing pipeline) ───────────────────
    img    = cv2.resize(img, (final_w, final_h))
    gray   = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh  = cv2.adaptiveThreshold(
        blurred, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV,
        11, 2
    )
    kernel  = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    # ── 2. Build template index ──────────────────────────────────
    index = build_bubble_index(template)

    # ── 3. Sample fill at every bubble position ──────────────────
    scores = {}

    for (px, py), meta in zip(bubble_coordinates, index):
        if meta["field"] not in ANSWER_FIELDS:
            continue
        fill = sample_fill(cleaned, px, py, meta["w"], meta["h"])
        q    = meta["question"]
        scores.setdefault(q, []).append((meta["value"], fill))

    # ── 4. Pick answer per question ──────────────────────────────
    detected = {}
    for q, choices in scores.items():
        print(f"Q{q}: " + "  ".join(f"{v}={f:.3f}" for v, f in choices))
        filled = [v for v, f in choices if f >= fill_threshold]
        if len(filled) == 1:
            detected[q] = filled[0]
        elif len(filled) == 0:
            continue          # blank
        else:
            detected[q] = "AMBIGUOUS"    # multiple bubbles marked

    return detected
        

# ── Core grading ──────────────────────────────────────────────────

def grading(img, bubble_coordinates, template,
            answer_key: dict | None = None,
            fill_threshold: float = 0.55,
            final_w: int = 2480, final_h: int = 3508):
    """
    Parameters
    ----------
    img               : original BGR scan
    bubble_coordinates: output of get_bubble_coordinates()
    template     : template dict
    answer_key        : { question_int: "A"/"B"/"C"/"D" }
                        pass None to just return detected answers
    fill_threshold    : min fill ratio to count a bubble as marked

    Returns
    -------
    {
        "answers":    { q: "A"/"B"/"C"/"D"/None/"AMBIGUOUS" },
        "score":      int,      # only if answer_key provided
        "total":      int,
        "percentage": float,
        "results":    { q: { student, expected, is_correct } },
    }
    """

    # ── 1. Preprocess (your existing pipeline) ───────────────────
    img    = cv2.resize(img, (final_w, final_h))
    gray   = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh  = cv2.adaptiveThreshold(
        blurred, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV,
        11, 2
    )
    kernel  = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    # ── 2. Build template index ──────────────────────────────────
    index = build_bubble_index(template)

    # ── 3. Sample fill at every bubble position ──────────────────
    scores = {}

    for (px, py), meta in zip(bubble_coordinates, index):
        if meta["field"] not in ANSWER_FIELDS:
            continue
        fill = sample_fill(cleaned, px, py, meta["w"], meta["h"])
        q    = meta["question"]
        scores.setdefault(q, []).append((meta["value"], fill))

    # ── 4. Pick answer per question ──────────────────────────────
    detected = {}
    for q, choices in scores.items():
        print(f"Q{q}: " + "  ".join(f"{v}={f:.3f}" for v, f in choices))
        filled = [v for v, f in choices if f >= fill_threshold]
        if len(filled) == 1:
            detected[q] = filled[0]
        elif len(filled) == 0:
            detected[q] = None           # blank
        else:
            detected[q] = "AMBIGUOUS"    # multiple bubbles marked

    result: dict = {"answers": detected}

    # ── 5. Score against answer key (optional) ───────────────────
    if answer_key:
        correct  = 0
        results: dict = {}
        for q, expected in answer_key.items():
            student = detected.get(q)
            ok      = (student == expected)
            if ok:
                correct += 1
            results[q] = {
                "student":    student,
                "expected":   expected,
                "is_correct": ok,
            }
        total = len(answer_key)
        result.update({
            "score":      correct,
            "total":      total,
            "percentage": round(correct / total * 100, 1) if total else 0.0,
            "results":    results,
        })

    return result


# ── Debug visualisation ───────────────────────────────────────────

def debug_view(img, bubble_coordinates, template,
               fill_threshold: float = 0.55,
               final_w: int = 2480, final_h: int = 3508):
    """
    Draws coloured rectangles on the cleaned image so you can
    visually verify alignment and fill detection.
      green  = detected as filled
      gray   = detected as blank
    Then calls print_image() so you can inspect it.
    """
    img     = cv2.resize(img, (final_w, final_h))
    gray    = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh  = cv2.adaptiveThreshold(
        blurred, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV,
        11, 2
    )
    kernel  = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    vis     = cv2.cvtColor(cleaned, cv2.COLOR_GRAY2BGR)

    index = build_bubble_index(template)

    for (px, py), meta in zip(bubble_coordinates, index):
        if meta["field"] not in ANSWER_FIELDS:
            continue
        cx, cy = int(round(px)), int(round(py))
        hw, hh = meta["w"] // 2, meta["h"] // 2
        fill   = sample_fill(cleaned, px, py, meta["w"], meta["h"])
        colour = (0, 220, 0) if fill >= fill_threshold else (100, 100, 100)
        cv2.rectangle(vis, (cx - hw, cy - hh), (cx + hw, cy + hh), colour, 2)
        cv2.putText(vis, f"{meta['value']}", (cx - hw, cy - hh - 3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, colour, 1)

    print_image(vis)


# ── Pretty report ─────────────────────────────────────────────────

def print_report(report: dict) -> None:
    print(f"\n{'─'*42}")
    if "score" in report:
        print(f"  Score : {report['score']} / {report['total']}"
              f"  ({report['percentage']}%)")
        print(f"{'─'*42}")
        for q, info in sorted(report["results"].items()):
            mark    = "✓" if info["is_correct"] else "✗"
            student = info["student"] or "—"
            print(f"  Q{q:3d}  student={student}  "
                  f"expected={info['expected']}  {mark}")
    else:
        print("  Detected answers (no key provided)")
        print(f"{'─'*42}")
        for q, ans in sorted(report["answers"].items()):
            print(f"  Q{q:3d}  {ans or '—'}")
    print(f"{'─'*42}\n")


def grading_wrapper(img, answer_key, template, fill_threshold=0.55):
    bubble_coordinates = get_bubble_coordinates(img, template)
    return grading(img, bubble_coordinates, template, answer_key, fill_threshold=fill_threshold)


# ── Entry point ───────────────────────────────────────────────────

if __name__ == "__main__":
    template_path = "./templates/CMS_mc_template.json"
    img_path      = "./samples/scans/2B_11.png"
    
    template = json.load(open(template_path, "r", encoding="utf-8"))
    img                = cv2.imread(img_path)
    bubble_coordinates = get_bubble_coordinates(img, template)
    ANSWER_KEY = generate_answer_key(img, get_bubble_coordinates(img, template), template)

    # Normal grading run
    report = grading(img, bubble_coordinates, template, ANSWER_KEY)
    print_report(report)

    # Uncomment to visualise fill detection before grading:
    debug_view(img, bubble_coordinates, template)