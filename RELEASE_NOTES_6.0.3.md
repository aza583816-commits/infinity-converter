# Infinity Converter 6.0.3 — Verified AI + Live UI hardening

- Fixed production 500 cascade by importing `render_template` in `app_factory.py`.
- Fixed Infinity AI catalog generation to use `_meta_for(tool)["slug"]` instead of a nonexistent `Tool.slug` field.
- Added persistent dark/light theme switching.
- Added a site-wide Infinity AI launcher and Gemini status check.
- Revalidated the 162-tool registry, static quality suite, Python 3.11 syntax, and JavaScript syntax.
- This release is not marked production-deployed until Railway performs a fresh deployment and the live Gemini `/ask` test passes.
