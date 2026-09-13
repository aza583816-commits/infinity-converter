# Infinity Converter 6.1.1 — AdSense Quality Hardening

This patch is intentionally focused on the previous AdSense **low-value content** rejection. It improves the site-side signals without changing the core converter experience or claiming approval is guaranteed.

## Changes

- Removed the public **coming soon / under construction** roadmap from the homepage.
- Replaced it with six original Knowledge Center guides and clear editorial context.
- Linked relevant curated guides from converter pages.
- Limited the AdSense serving script to content-rich, indexable pages; account verification metadata remains available globally.
- Suppressed both Auto Ads script loading and manual ad-unit rendering on error, auth/account, collection, browser-tool, developer-tool and other intentionally noindex surfaces.
- Reduced the sitemap to the strongest publisher-content pages, 15 original guides, and a curated set of converter pages. All tools remain available to users from `/tools`.
- Added `noindex,follow` to deliberately thin utility surfaces while preserving navigation and functionality.
- Corrected Arabic/English canonical + hreflang alignment.
- Added legacy redirects for old unit-converter URLs still being crawled, reducing dead-end 404 traffic.
- Added regression tests for the quality-hardening rules.

## AdSense note

The production environment must keep `ADSENSE_CLIENT_ID=ca-pub-...` configured. Manual ad-unit slot variables may remain blank when using Auto ads. Google makes the final approval decision.
