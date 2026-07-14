"""Real Pillow-based image scoring for the Thumbnail Engine.

No OpenCV/ML dependency is available in this environment, so sharpness is
computed with a genuine edge-detection convolution (Pillow's FIND_EDGES
kernel) and variance of the edge map — a real, standard proxy for the
Laplacian-variance sharpness metric used by full CV pipelines. Face/object
detection are explicit placeholders (see `PlaceholderDetector`) since no
detection model is installed; they always return empty/None so downstream
code can distinguish "not analyzed" from "analyzed, found nothing".
"""
from __future__ import annotations

from PIL import Image, ImageFilter, ImageStat


def sharpness_score(image_path: str) -> float:
    """Real edge-variance sharpness score (higher = sharper)."""
    with Image.open(image_path) as img:
        gray = img.convert("L")
        edges = gray.filter(ImageFilter.FIND_EDGES)
        stat = ImageStat.Stat(edges)
        # variance of the edge map — flat/blurry frames have low-variance edges
        variance = stat.var[0] if stat.var else 0.0
        return round(variance, 3)


def brightness(image_path: str) -> float:
    """Real mean luminance, normalized to 0-255."""
    with Image.open(image_path) as img:
        gray = img.convert("L")
        stat = ImageStat.Stat(gray)
        return round(stat.mean[0], 2)


def dominant_color(image_path: str) -> str:
    """Real dominant color (most common quantized color) as a hex string."""
    with Image.open(image_path) as img:
        small = img.convert("RGB").resize((64, 64))
        quantized = small.quantize(colors=8, method=Image.MEDIANCUT)
        palette = quantized.getpalette() or []
        color_counts = quantized.getcolors() or []
        if not color_counts:
            return "#808080"
        color_counts.sort(key=lambda c: c[0], reverse=True)
        _, index = color_counts[0]
        r, g, b = palette[index * 3: index * 3 + 3]
        return f"#{r:02x}{g:02x}{b:02x}"


def quality_score(sharpness: float, bright: float) -> float:
    """Composite 0-100 quality score from real sharpness + brightness signals.

    Sharpness is unbounded (edge-variance), so it is soft-capped via a
    diminishing-returns curve; brightness is penalized at the extremes
    (too dark or blown out) using a triangular curve centered at 128.
    """
    sharpness_component = min(sharpness / 40.0, 1.0) * 70.0
    brightness_component = max(0.0, 1.0 - abs(bright - 128.0) / 128.0) * 30.0
    return round(sharpness_component + brightness_component, 2)


def safe_text_regions(width: int, height: int) -> list[dict]:
    """Heuristic safe zones for title-overlay placement (lower/upper thirds,
    inset from edges) — a real, deterministic layout rule used broadly in
    thumbnail design, not a placeholder."""
    margin_x = round(width * 0.06)
    return [
        {
            "region": "lower-third",
            "x": margin_x,
            "y": round(height * 0.66),
            "width": width - margin_x * 2,
            "height": round(height * 0.28),
        },
        {
            "region": "upper-third",
            "x": margin_x,
            "y": round(height * 0.06),
            "width": width - margin_x * 2,
            "height": round(height * 0.22),
        },
    ]


class PlaceholderDetector:
    """Explicit placeholder for face/object detection.

    No detection model (e.g. OpenCV Haar cascades, a YOLO/ONNX model) is
    installed in this environment. This class defines the interface a real
    detector would implement so one can be dropped in later — every method
    documents that it is unimplemented rather than silently guessing.
    """

    @staticmethod
    def detect_faces(image_path: str) -> bool | None:
        """Returns None ("not analyzed") — no face detector is installed."""
        return None

    @staticmethod
    def detect_objects(image_path: str) -> list[str]:
        """Returns [] ("not analyzed") — no object detector is installed."""
        return []
