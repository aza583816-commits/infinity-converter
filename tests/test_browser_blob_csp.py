"""The browser image editor loads a local File using a blob: image URL.

Allow only image blob URLs; keep script-src and object-src locked down.
"""
from app_factory import create_app


def test_browser_image_editor_csp_allows_local_blob_image_loading():
    response = create_app().test_client().get("/browser-tools/light-background-cleanup")
    assert response.status_code == 200
    policy = response.headers["Content-Security-Policy"]
    directives = {chunk.strip().split(" ", 1)[0]: chunk.strip() for chunk in policy.split(";") if chunk.strip()}
    assert "blob:" in directives["img-src"].split(), "Local image preview blocked by CSP"
    assert "blob:" not in directives["script-src"].split()
    assert directives["object-src"] == "object-src 'none'"
