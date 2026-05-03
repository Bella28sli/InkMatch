from __future__ import annotations

from io import BytesIO
from math import cos, pi, sqrt
from statistics import median

try:
    from PIL import Image
except ImportError:  # pragma: no cover - optional dependency guard
    Image = None  # type: ignore[assignment]


def _dct_coefficient(pixels: list[float], size: int, u: int, v: int) -> float:
    alpha_u = sqrt(1 / size) if u == 0 else sqrt(2 / size)
    alpha_v = sqrt(1 / size) if v == 0 else sqrt(2 / size)
    total = 0.0
    for y in range(size):
        for x in range(size):
            total += (
                pixels[y * size + x]
                * cos(((2 * x + 1) * u * pi) / (2 * size))
                * cos(((2 * y + 1) * v * pi) / (2 * size))
            )
    return alpha_u * alpha_v * total


def compute_phash(content: bytes) -> str | None:
    if Image is None or not content:
        return None

    try:
        with Image.open(BytesIO(content)) as image:
            gray = image.convert('L').resize((32, 32), Image.Resampling.LANCZOS)
            pixels = [float(value) for value in gray.getdata()]
    except Exception:
        return None

    if not pixels:
        return None

    low_freq = [_dct_coefficient(pixels, 32, u, v) for v in range(8) for u in range(8)]
    threshold = median(low_freq[1:])
    bits = ''.join('1' if value >= threshold else '0' for value in low_freq)
    return f'{int(bits, 2):016x}'
