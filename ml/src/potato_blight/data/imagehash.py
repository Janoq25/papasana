"""dHash de 64 bits compatible con el backend."""

from PIL import Image


def dhash(image: Image.Image) -> int:
    small = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(small.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | int(pixels[row * 9 + col] > pixels[row * 9 + col + 1])
    return bits


def hamming(a: int, b: int) -> int:
    return (int(a) ^ int(b)).bit_count()
