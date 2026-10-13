# chaos-eng.com

Site of Chaos Engineering, bilingual (FR at `/`, EN at `/en/`), static, served by GitHub Pages from `main:/docs`.

## Build

```
python tools/lattice.py   # only when the hero lattice, social image or favicons change (numpy, scipy, Pillow)
python build.py           # regenerate docs/ (standard library only)
python build.py --release # same, but fails on placeholders, broken links, em dashes
python build.py --release --preview-path chaos-eng.com
                          # for the provisional address jdirr.github.io/chaos-eng.com (no CNAME, noindex)
```

Deploy: commit `docs/` and push `main`; GitHub Pages publishes `main:/docs`.

Preview: `python -m http.server 8765 --directory docs`, then http://127.0.0.1:8765/.

## Layout

- `content/{fr,en}/*.html`: page bodies; the leading comment holds `title` and `description`.
  `{{url:key}}` links to a page in the same language, `{{> name}}` inlines `templates/partials/name.svg`.
- `templates/base.html`: shared head, header, footer.
- `static/`: CSS, self-hosted fonts (Inter, Space Grotesk, OFL), images; copied as is into `docs/`.
- `build.py`: page table (`PAGES`), redirects from the old WordPress URLs (`REDIRECTS`), UI strings, sitemap and checks.
- French typography (non-breaking spaces before `; : ? !`) is applied by the build: write plain spaces.

## Open items

- DNS switch from WordPress.com hosting to GitHub Pages: keep the MX record (`smtp-fwd.wordpress.com`), which forwards contact@.
