from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_base_has_search_social_and_adsense_metadata():
    base = read("templates/base.html")
    assert 'rel="icon" type="image/png"' in base
    assert 'og:image' in base
    assert 'twitter:card' in base
    assert 'google-adsense-account' in base
    assert 'application/ld+json' in base


def test_ads_txt_is_dynamic_and_never_uses_a_fake_publisher_id():
    pages = read("api/pages.py")
    assert 'def ads_txt()' in pages
    assert 'ADSENSE_CLIENT_ID' in pages
    assert 'f08c47fec0942fa0' in pages
    assert 'abort(404)' in pages


def test_brand_assets_are_real_images():
    from PIL import Image
    for name, size in (("static/icon-192.png", (192, 192)), ("static/icon-512.png", (512, 512)), ("static/og-banner.png", (1200, 630))):
        with Image.open(ROOT / name) as image:
            assert image.size == size
            image.verify()
