"""Pruebas unitarias de dominio: categorización (D-01), dHash y EXIF/GPS."""

import io

import pytest
from PIL import ExifTags, Image
from PIL.TiffImagePlugin import IFDRational

from app.domain.images import InvalidImageError, dhash, hamming, inspect_image
from app.domain.labels import categorize


def noise_jpeg(size=(400, 300), exif=None, brightness=1.0) -> bytes:
    img = Image.effect_noise(size, 60).convert("RGB")
    if brightness != 1.0:
        img = img.point(lambda v: min(255, int(v * brightness)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, **({"exif": exif} if exif is not None else {}))
    return buf.getvalue()


def gps_exif(lat: float, lon: float) -> Image.Exif:
    def dms(value: float):
        value = abs(value)
        d = int(value)
        m = int((value - d) * 60)
        s = (value - d - m / 60) * 3600
        return (IFDRational(d, 1), IFDRational(m, 1), IFDRational(round(s * 1000), 1000))

    exif = Image.Exif()
    exif[ExifTags.Base.Make] = "CamaraPrueba"
    exif[ExifTags.Base.Model] = "X1"
    exif[ExifTags.Base.DateTime] = "2026:10:30 08:15:00"
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    gps[1] = "S" if lat < 0 else "N"
    gps[2] = dms(lat)
    gps[3] = "W" if lon < 0 else "E"
    gps[4] = dms(lon)
    return exif


@pytest.mark.parametrize("pred,conf,expected", [
    ("sano", 0.95, ("sano", False, "automatico")),
    ("sano", 0.50, ("sospechoso", True, "pendiente_revision")),
    ("sintomas_compatibles_tizon_tardio", 0.90, ("tizon_tardio_compatible", False, "pendiente_revision")),
    ("sintomas_compatibles_tizon_tardio", 0.69, ("sospechoso", True, "pendiente_revision")),
    ("otra_enfermedad_foliar", 0.99, ("sospechoso", False, "pendiente_revision")),
])
def test_categorizacion_por_sintoma(pred, conf, expected):
    assert categorize(pred, conf, 0.70) == expected


def test_dhash_estable_ante_cambios_de_brillo_y_distinto_entre_imagenes():
    a = Image.effect_noise((300, 300), 60).convert("RGB")
    b = a.point(lambda v: min(255, int(v * 1.05)))
    c = Image.effect_noise((300, 300), 60).convert("RGB")
    assert hamming(dhash(a), dhash(b)) <= 6
    assert hamming(dhash(a), dhash(c)) > 10
    assert -(1 << 63) <= dhash(a) < (1 << 63)  # cabe en BIGINT


def test_exif_gps_y_fecha():
    info = inspect_image(noise_jpeg(exif=gps_exif(-12.01535, -75.2899)))
    assert info.lat == pytest.approx(-12.01535, abs=1e-5)
    assert info.lon == pytest.approx(-75.2899, abs=1e-5)
    assert info.captured_at is not None and info.captured_at.year == 2026
    assert info.exif["fabricante"] == "CamaraPrueba" and info.exif["tiene_gps"] is True


def test_imagen_sin_exif_y_formatos_invalidos():
    info = inspect_image(noise_jpeg())
    assert info.lat is None and info.exif == {}
    with pytest.raises(InvalidImageError):
        inspect_image(b"GIF89a no soportado")
    small = io.BytesIO()
    Image.new("RGB", (20, 20)).save(small, format="PNG")
    with pytest.raises(InvalidImageError, match="pequeña"):
        inspect_image(small.getvalue())
