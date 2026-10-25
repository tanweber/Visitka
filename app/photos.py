"""Фото контактов: приводим любую загрузку к квадратному JPEG 512×512."""
from __future__ import annotations

import math
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

# защита от «бомб» распаковки: больше 40 Мп не открываем
Image.MAX_IMAGE_PIXELS = 40_000_000

MAX_UPLOAD = 15 * 1024 * 1024
SIZE = 512


class PhotoError(ValueError):
    pass


def parse_crop(value: str) -> tuple[float, float, float] | None:
    """«x,y,s» из окна обрезки: левый верхний угол (доли ширины и высоты)
    и сторона квадрата (доля меньшей стороны). Мусор — None, будет обрезка по центру."""
    try:
        x, y, s = (float(v) for v in value.split(","))
    except ValueError:
        return None
    if not all(math.isfinite(v) for v in (x, y, s)) or not (0 < s <= 1 and 0 <= x <= 1 and 0 <= y <= 1):
        return None
    return x, y, s


def normalize(data: bytes, crop: tuple[float, float, float] | None = None) -> bytes:
    """Поворот по EXIF, обрезка в квадрат (выбранная или по центру), JPEG без метаданных."""
    if not data:
        raise PhotoError("пустой файл")
    if len(data) > MAX_UPLOAD:
        raise PhotoError("файл больше 15 МБ")
    try:
        with Image.open(BytesIO(data)) as im:
            if im.format not in {"JPEG", "PNG", "WEBP", "GIF"}:
                raise PhotoError("нужен JPEG, PNG, WebP или GIF")
            # JPEG можно декодировать сразу в уменьшенном виде — в разы меньше памяти
            # при сильном увеличении нужно больше пикселей исходника
            need = math.ceil(SIZE * 2 / crop[2]) if crop else SIZE * 2
            im.draft("RGB", (need, need))
            im = ImageOps.exif_transpose(im)
            if im.mode in ("RGBA", "LA", "P"):
                rgba = im.convert("RGBA")
                im = Image.new("RGB", rgba.size, (255, 255, 255))
                im.paste(rgba, mask=rgba.getchannel("A"))
            else:
                im = im.convert("RGB")
            if crop:
                width, height = im.size
                side = max(1, round(crop[2] * min(width, height)))
                left = min(max(0, round(crop[0] * width)), width - side)
                top = min(max(0, round(crop[1] * height)), height - side)
                im = im.crop((left, top, left + side, top + side))
            im = ImageOps.fit(im, (SIZE, SIZE), Image.Resampling.LANCZOS)
            out = BytesIO()
            im.save(out, "JPEG", quality=85, optimize=True, progressive=True)
            return out.getvalue()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise PhotoError("не удалось прочитать изображение") from exc
