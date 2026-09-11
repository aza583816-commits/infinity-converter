# AdSense readiness — Infinity Converter 6.1.0

Reviewed: 2026-09-11

This release is engineered to be **submission-ready from the site side**, not to guarantee approval. Google makes the final decision and can change policies.

## Implemented in the codebase
- Clear navigation to Tools, Knowledge Center, About, Contact, Privacy, Terms, Cookies, and How it works.
- Original Knowledge Center articles with useful file-work guidance and matching tool links.
- Honest processing/privacy language: browser-side and temporary server-side processing are distinguished instead of claiming every tool is local.
- Google AdSense loader is **disabled unless a real `ADSENSE_CLIENT_ID` is configured**.
- `ads.txt` returns 404 until a valid `ca-pub-...` publisher ID is present, then emits Google's authorized-seller line.
- Ad slots render only when both a publisher ID and a real slot ID are configured. No fake IDs are bundled.
- Ad placements are visually labelled and separated from conversion/download controls.
- Home, tool, and article placements are optional; the site remains fully usable with ads disabled.
- Security headers, canonical URLs, hreflang, sitemap, robots, Organization/Article structured data, PWA metadata, and social preview assets are present.
- Mobile/iPad layouts, keyboard focus styles, reduced-motion support, and light/dark themes are included.
- Public auth and billing remain hidden by default until they are genuinely ready.

## Before submitting to AdSense
1. Set `GOOGLE_SITE_VERIFICATION` and the real `ADSENSE_CLIENT_ID` only from your own Google account.
2. Confirm the deployed `ads.txt`, sitemap, robots, About, Contact, Privacy, Terms, Cookies, and article pages are publicly reachable.
3. Review every public page for substantial, original value and remove any unfinished/placeholder routes from navigation.
4. Keep ads away from download/convert controls and never encourage ad clicks.
5. If serving personalised ads to users in the EEA, UK, or Switzerland, configure a **Google-certified CMP** (Google's own CMP in AdSense Privacy & messaging is one option) and verify the consent flow before enabling those ads.
6. Re-run the production smoke/AI checks after the final Railway deployment.

## Approval reality
The implementation removes common technical and UX blockers, but approval can still depend on content quality, traffic/site history, policy review, account eligibility, regional requirements, and Google's reviewer/automated systems.
