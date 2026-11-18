"""Validación de imágenes, metadatos EXIF/GPS y hash perceptual (dHash de 64 bits)."""

import hashlib
import io
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import ExifTags, Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
EXTENSIONS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
MAX_PIXELS = 40_000_000  # protección ante "decompression bombs"
MIN_SIDE = 64
LIMA = ZoneInfo("America/Lima")

Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class InvalidImageError(ValueError):
    pass


@dataclass
class ImageInfo:
    format: str
    mime: str
    extension: str
    width: int
    height: int
    sha256: str
    phash: int  # con signo (cabe en BIGINT)
    exif: dict = field(default_factory=dict)
    captured_at: datetime | None = None
    lat: float | None = None
    lon: float | None = None


def _rational(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError, ZeroDivisionError):
        num, den = v
        return float(num) / float(den)


def _dms_to_deg(dms, ref) -> float | None:
    try:
        d, m, s = (_rational(x) for x in dms)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    deg = d + m / 60 + s / 3600
    if isinstance(ref, bytes):
        ref = ref.decode(errors="ignore")
    return -deg if str(ref).upper() in ("S", "W") else deg


def dhash(img: Image.Image) -> int:
    """Hash perceptual por diferencias (dHash) de 64 bits, devuelto con signo para BIGINT."""
    small = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    px = list(small.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            left = px[row * 9 + col]
            right = px[row * 9 + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return bits - (1 << 64) if bits >= (1 << 63) else bits


def hamming(a: int, b: int) -> int:
    return bin((a ^ b) & ((1 << 64) - 1)).count("1")


def inspect_image(raw: bytes) -> ImageInfo:
    try:
        img = Image.open(io.BytesIO(raw))
        fmt = img.format
        img.verify()
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise InvalidImageError("El archivo no es una imagen válida o es demasiado grande.") from e
    if fmt not in ALLOWED_FORMATS:
        raise InvalidImageError("Formato no permitido. Use JPEG, PNG o WebP.")

    exif_raw = img.getexif()
    upright = ImageOps.exif_transpose(img)
    w, h = upright.size
    if min(w, h) < MIN_SIDE:
        raise InvalidImageError(f"La imagen es demasiado pequeña (mínimo {MIN_SIDE} px por lado).")

    info = ImageInfo(
        format=fmt, mime=ALLOWED_FORMATS[fmt], extension=EXTENSIONS[fmt], width=w, height=h,
        sha256=hashlib.sha256(raw).hexdigest(), phash=dhash(upright),
    )

    if exif_raw:
        make = exif_raw.get(ExifTags.Base.Make)
        model = exif_raw.get(ExifTags.Base.Model)
        exif_ifd = exif_raw.get_ifd(ExifTags.IFD.Exif)
        original = exif_ifd.get(ExifTags.Base.DateTimeOriginal) or exif_raw.get(ExifTags.Base.DateTime)
        if original:
            try:
                info.captured_at = datetime.strptime(str(original).strip(), "%Y:%m:%d %H:%M:%S").replace(tzinfo=LIMA)
            except ValueError:
                pass
        gps = exif_raw.get_ifd(ExifTags.IFD.GPSInfo)
        if gps:
            lat = _dms_to_deg(gps.get(2), gps.get(1)) if gps.get(2) else None
            lon = _dms_to_deg(gps.get(4), gps.get(3)) if gps.get(4) else None
            if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
                info.lat, info.lon = lat, lon
        # Solo metadatos útiles para la procedencia (no se guarda el EXIF completo)
        info.exif = {k: v for k, v in {
            "fabricante": str(make).strip() if make else None,
            "modelo": str(model).strip() if model else None,
            "fecha_original": str(original).strip() if original else None,
            "tiene_gps": info.lat is not None,
            "orientacion": exif_raw.get(ExifTags.Base.Orientation),
        }.items() if v is not None}
    return info
