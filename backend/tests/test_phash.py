import io

from app.document_processing.forensics_image import hamming_distance_hex, phash_hex


def _jpeg(color):
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color=color).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def test_identical_phash():
    a = _jpeg((10, 20, 30))
    h1 = phash_hex(a)
    h2 = phash_hex(a)
    assert h1 is not None and h2 is not None
    assert hamming_distance_hex(h1, h2) == 0


def test_different_images_distance():
    from PIL import Image

    def patterned(seed: int) -> bytes:
        img = Image.new("RGB", (64, 64))
        pixels = img.load()
        for x in range(64):
            for y in range(64):
                pixels[x, y] = ((x * seed) % 256, (y * seed * 3) % 256, (x + y + seed) % 256)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return buf.getvalue()

    h1 = phash_hex(patterned(1))
    h2 = phash_hex(patterned(17))
    assert h1 and h2
    assert hamming_distance_hex(h1, h2) > 0
