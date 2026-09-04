# AdSense readiness — Infinity Converter 6.0.1

This release prepares the site technically for Google AdSense without inventing or hard-coding a publisher ID.

## Included

- Google-friendly favicon PNG at `/static/icon-192.png` and `/static/icon-512.png`.
- Social sharing image at `/static/og-banner.png` (1200×630).
- Open Graph and Twitter image metadata.
- Organization JSON-LD with the site logo.
- `robots` metadata and an existing crawlable `sitemap.xml`.
- Privacy/cookie disclosures covering Google advertising cookies and related technologies.
- Optional AdSense account meta tag and loader, enabled only when `ADSENSE_CLIENT_ID` is configured.
- Strict nonce-based CSP path for AdSense compatibility.
- Dynamic `/ads.txt` using the real configured publisher ID only.
- Optional `GOOGLE_SITE_VERIFICATION` environment variable for Search Console verification.

## Railway variables

Set these only after obtaining the real values from Google:

```text
ADSENSE_CLIENT_ID=ca-pub-XXXXXXXXXXXXXXXX
GOOGLE_SITE_VERIFICATION=YOUR_REAL_SEARCH_CONSOLE_TOKEN
```

Never put a real Google publisher ID or verification token in source code unless you intentionally want it public. Never put API secrets in Git.

## Important

Technical readiness cannot guarantee AdSense approval. Google also reviews the live site for original, useful content, clear navigation, policy compliance, and overall user experience.

For traffic from the EEA, UK, or Switzerland where personalised advertising is served, configure a Google-certified consent management platform (CMP) from the AdSense/Privacy & messaging area of the account.
