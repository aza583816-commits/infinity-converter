# Post-launch verification checklist

- [x] GitHub production quality gates green
- [x] Railway deployed the PR #16 merge commit
- [x] Production readiness endpoint healthy
- [x] Workflow/trust/vitals assets served in production
- [x] Legacy URL redirects observed in live production logs
- [x] Gunicorn worker recycling confirmed intentional
- [x] Pillow metadata-strip deprecation removed with regression coverage
- [ ] Shared Redis enabled before horizontal scaling
- [ ] Dedicated network-isolated renderer worker verified
- [ ] GA4 connected account-side
- [ ] Google-certified CMP verified live
- [ ] Historical HTTP sitemap retired in Search Console and recrawl checked
