# Infinity Converter 6.1.2 — AdSense final checklist

Do not request another review until the deployed 6.1.2 release passes these production checks.

- Railway deployment is `SUCCESS` and build log ends with `Production preflight PASS`.
- `/api/v2/healthz` returns 200 and reports version `6.1.2`.
- `/ads.txt` returns the real publisher record from the Railway `ADSENSE_CLIENT_ID` variable.
- `/robots.txt` returns 200 and includes the sitemap URL.
- `/sitemap.xml` contains core publisher pages, 15 articles, Trust/Editorial pages, and only the 21 reviewed converter pages.
- Representative reviewed converter pages are `index,follow` and load the AdSense serving script when the publisher ID is configured.
- Representative unreviewed converter/browser/developer pages remain usable but are `noindex,follow` and do not load the AdSense serving script.
- A random 404 remains a real HTTP 404, carries `noindex,follow`, and does not load Google ad serving.
- Arabic and English (`?lang=en`) alternates render with matching canonical/hreflang metadata.
- Safe sample buttons work on several reviewed tools, including one OCR/Office workflow and PDF redaction/password protection.
- Infinity AI status is healthy in the browser and does not remain stuck on the initial connection message.
- On mobile/iPad/desktop, the redesign remains readable, motion stays subtle, and reduced-motion preference disables decorative animation.
- In AdSense > Privacy & messaging, configure/use a Google-certified CMP where required for EEA/UK/Switzerland ad traffic.
- Submit the refreshed sitemap in Google Search Console and request indexing for the homepage plus representative article/reviewed-tool URLs.
- Allow Google time to recrawl the new version before pressing the AdSense re-review button.

No checklist can guarantee approval; this is the release gate for eliminating avoidable site-side issues before Google reviews the site again.
