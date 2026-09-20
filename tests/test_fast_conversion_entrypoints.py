"""Regression guards for direct-to-conversion navigation and page hierarchy."""
from app_factory import create_app


def test_home_popular_tools_are_first_class_and_have_live_routes():
    app = create_app()
    with app.test_client() as client:
        home = client.get("/?lang=en")
        assert home.status_code == 200
        markup = home.get_data(as_text=True)
        assert 'class="v8-quick-tools"' in markup
        assert markup.index('class="v8-quick-tools"') < markup.index('id="infinity-ai"')
        for slug in ("pdf-to-docx", "word-to-pdf", "merge-pdf", "compress-pdf"):
            assert f'href="/tools/{slug}"' in markup
            response = client.get(f"/tools/{slug}?lang=en")
            assert response.status_code == 200, (slug, response.status_code)


def test_upload_and_action_appear_before_processing_explanation():
    app = create_app()
    with app.test_client() as client:
        for slug in ("word-to-pdf", "pdf-to-docx"):
            html = client.get(f"/tools/{slug}?lang=en").get_data(as_text=True)
            assert html.index('id="converter-form"') < html.index('id="processing-title"')
            assert html.index('id="result-panel"') < html.index('id="processing-title"')
            assert 'id="files"' in html
