import io

from app.document_processing.forensics_image import ela_anomaly_score


def test_ela_on_jpeg():
    try:
        from PIL import Image
    except ImportError:
        assert ela_anomaly_score(b"not-an-image") == 0.0
        return
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=(120, 80, 40)).save(buf, format="JPEG", quality=90)
    score = ela_anomaly_score(buf.getvalue())
    assert 0.0 <= score <= 1.0
