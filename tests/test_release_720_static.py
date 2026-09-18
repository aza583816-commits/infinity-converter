from pathlib import Path

from core.tooling import TOOLS
from converters.operations import operation_ids

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_runtime_version_is_consistent():
    import json
    from config.settings import settings
    version = settings.app_version
    assert f'APP_VERSION={version}' in read('.env.example')
    assert json.loads(read('manifest.json'))['version'] == version
    sw = read('static/sw.js')
    assert f'infinity-static-v{version}' in sw
    assert f'app.js?v={version}' in sw
    assert f'manifest.json?v={version}' in sw
    assert 'data-release="{{ app_version }}"' in read('templates/base.html')


def test_720_registry_and_backend_are_one_to_one():
    assert len(TOOLS) == 162
    assert len(operation_ids()) == 162
    assert set(TOOLS) == set(operation_ids())


def test_720_output_contract_is_enforced():
    engine = read('converters/engine.py')
    assert '_declared_output_guard' in engine
    assert 'tool.output_ext' in engine
    assert 'MIME_BY_EXTENSION' in engine
    handlers = read('converters/legacy_handlers.py')
    assert '-resized.jpg' in handlers
    assert '-compressed.jpg' in handlers
    assert '-rotated.jpg' in handlers


def test_720_language_policy_is_device_based_not_geolocation():
    source = read('i18n/__init__.py')
    assert 'DEFAULT_LANGUAGE = "en"' in source
    assert 'Accept-Language' in source
    assert 'primary.startswith("ar-")' in source
    assert 'primary.startswith("en-")' in source
    assert 'remote_addr' not in source
    assert 'X-Forwarded-For' not in source


def test_720_future_entitlements_are_guarded_while_public_defaults_stay_free():
    routes = read('api/routes.py')
    assert 'tool.id in PREMIUM_TOOL_IDS' in routes
    assert 'PUBLIC_AUTH_ENABLED' in routes
    env = read('.env.example')
    assert 'PUBLIC_AUTH_ENABLED=0' in env
    assert 'PUBLIC_BILLING_ENABLED=0' in env


def test_720_visual_cohesion_layer_covers_shared_surfaces():
    css = read('static/css/app.css')
    assert 'Infinity Converter 8.0.0 — Smart Workspace cohesion' in css
    for selector in (
        '.listing-head', '.collection-hero', '.blog-hero', '.how-hero',
        '.blog-article', '.auth-form', '.pricing-grid', '.developer-workspace',
        '.site-footer.v7-footer', '@media(max-width:640px)', '@media(prefers-reduced-motion:reduce)'
    ):
        assert selector in css


def test_720_production_gates_remain_enabled():
    docker = read('Dockerfile')
    preflight = read('scripts/preflight.py')
    assert 'RUN python scripts/preflight.py' in docker
    assert 'pytest -q' in docker
    assert 'all 162 public tool pages resolve OK' in preflight
    assert 'representative conversion word-to-pdf' not in preflight  # dynamic helper, not a hard-coded fake success
    assert 'real_conversion("word-to-pdf"' in preflight
    assert 'unsupported browser language fallback policy failed' in preflight
