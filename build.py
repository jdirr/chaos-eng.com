"""Build chaos-eng.com into docs/ (served by GitHub Pages from main:/docs).

Usage:
  python build.py            build, report warnings
  python build.py --release  build, fail on any warning (placeholders, broken links, style)
  python build.py --preview-path chaos-eng.com
                             build for the provisional address jdirr.github.io/chaos-eng.com:
                             links prefixed, no CNAME, pages marked noindex
"""
import hashlib
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs"
BASE = "https://chaos-eng.com"
DOMAIN = "chaos-eng.com"

# page key -> output path per language
PAGES = {
    "home": {"fr": "", "en": "en/"},
    "about": {"fr": "a-propos/", "en": "en/about/"},
    "contact": {"fr": "contact/", "en": "en/contact/"},
    "legal": {"fr": "mentions-legales/", "en": "en/legal-notice/"},
}
# old WordPress URLs -> new pages
REDIRECTS = {"about/": "/a-propos/", "contactez-nous/": "/contact/"}

STRINGS = {
    "fr": {
        "t_skip": "Aller au contenu", "t_menu": "Ouvrir le menu", "t_nav": "Navigation principale",
        "t_tagline": "Conseil scientifique en matériaux et procédés.", "t_site": "Le site",
        "t_info": "Informations", "t_legal": "Mentions légales et confidentialité",
        "t_rights": "Tous droits réservés.", "og_locale": "fr_FR",
        "alt_name": "English version", "alt_short": "EN",
        "nav": [("Services", "home", "#services"), ("Expertise", "home", "#expertise"),
                ("À propos", "about", ""), ("Contact", "contact", "")],
        "footer": [("Accueil", "home", ""), ("Services", "home", "#services"),
                   ("Expertise", "home", "#expertise"), ("À propos", "about", ""), ("Contact", "contact", "")],
    },
    "en": {
        "t_skip": "Skip to content", "t_menu": "Open menu", "t_nav": "Main navigation",
        "t_tagline": "Scientific consulting in materials and processes.", "t_site": "Site",
        "t_info": "Information", "t_legal": "Legal notice and privacy",
        "t_rights": "All rights reserved.", "og_locale": "en_GB",
        "alt_name": "Version française", "alt_short": "FR",
        "nav": [("Services", "home", "#services"), ("Expertise", "home", "#expertise"),
                ("About", "about", ""), ("Contact", "contact", "")],
        "footer": [("Home", "home", ""), ("Services", "home", "#services"),
                   ("Expertise", "home", "#expertise"), ("About", "about", ""), ("Contact", "contact", "")],
    },
}

warnings = []
ROOT_PATH = ""  # URL prefix; empty on chaos-eng.com, "/chaos-eng.com" on the provisional address


def url(key, lang):
    return ROOT_PATH + "/" + PAGES[key][lang]


def canon(key, lang):
    return BASE + "/" + PAGES[key][lang]


def read_page(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"\s*<!--(.*?)-->\s*", text, re.S)
    meta = {}
    for line in m.group(1).strip().splitlines():
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip()
    return meta, text[m.end():]


def french_typography(html):
    """Non-breaking spaces before high punctuation, in text nodes only."""
    def fix(s):
        s = re.sub(r" ([?!;])", " \\1", s)
        s = re.sub(r" :", " :", s)
        s = s.replace("« ", "« ").replace(" »", " »")
        return s
    parts = re.split(r"(<[^>]+>)", html)
    return "".join(p if p.startswith("<") else fix(p) for p in parts)


def expand(html, lang):
    partials = ROOT / "templates" / "partials"
    html = re.sub(r"\{\{>\s*([\w-]+)\s*\}\}", lambda m: (partials / f"{m.group(1)}.svg").read_text(encoding="utf-8").strip(), html)
    html = re.sub(r"\{\{url:(\w+)\}\}", lambda m: url(m.group(1), lang), html)
    return html.replace("{{root}}", ROOT_PATH)


def esc(s):
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def render(tpl, ctx):
    def sub(m):
        k = m.group(1)
        if k not in ctx:
            raise KeyError(f"template variable {k!r} missing")
        return str(ctx[k])
    return re.sub(r"\{\{(\w+)\}\}", sub, tpl)


def jsonld(lang, description):
    data = {
        "@context": "https://schema.org",
        "@type": "ProfessionalService",
        "name": "Chaos Engineering",
        "url": canon("home", lang),
        "logo": BASE + "/img/logo-512.png",
        "image": BASE + "/img/og.jpg",
        "email": "contact@chaos-eng.com",
        "description": description,
        "address": {"@type": "PostalAddress", "streetAddress": "224 rue des Pyrénées",
                    "postalCode": "75020", "addressLocality": "Paris", "addressCountry": "FR"},
        "founder": {"@type": "Person", "name": "Justin Dirrenberger",
                    "sameAs": ["https://www.linkedin.com/in/justindirrenberger/"]},
    }
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + "</script>"


def build_page(tpl, key, lang, version):
    meta, body = read_page(ROOT / "content" / lang / f"{key}.html")
    if lang == "fr":
        body = french_typography(body)
        meta = {k: french_typography(v) for k, v in meta.items()}
    body = expand(body, lang)
    s = STRINGS[lang]
    alt = "en" if lang == "fr" else "fr"

    def nav_link(label, k, frag, cls=""):
        cur = ' aria-current="page"' if k == key and not frag and k != "home" else ""
        c = f' class="{cls}"' if cls else ""
        return f'      <a href="{url(k, lang)}{frag}"{c}{cur}>{label}</a>'

    nav = [nav_link(l, k, f, "cta" if k == "contact" else "") for l, k, f in s["nav"]]
    nav.append(f'      <a class="lang" href="{url(key, alt)}" hreflang="{alt}" lang="{alt}" '
               f'title="{s["alt_name"]}">{s["alt_short"]}</a>')
    footer = [f'        <li><a href="{url(k, lang)}{f}">{l}</a></li>' for l, k, f in s["footer"]]
    alternates = "\n".join(
        [f'<link rel="alternate" hreflang="{lg}" href="{canon(key, lg)}">' for lg in ("fr", "en")]
        + [f'<link rel="alternate" hreflang="x-default" href="{canon(key, "fr")}">']
        + (['<meta name="robots" content="noindex">'] if ROOT_PATH else []))
    ctx = {
        **{k: v for k, v in s.items() if k.startswith("t_") or k in ("og_locale", "alt_name")},
        "lang": lang, "title": esc(meta["title"]), "og_title": esc(meta["title"].split(" | ")[0]),
        "description": esc(meta["description"]), "canonical": canon(key, lang), "base": BASE, "root": ROOT_PATH,
        "alternates": alternates, "version": version, "page_class": f"page-{key}",
        "home_url": url("home", lang), "legal_url": url("legal", lang),
        "alt_url": url(key, alt), "alt_lang": alt,
        "nav": "\n".join(nav), "footer_nav": "\n".join(footer),
        "jsonld": jsonld(lang, meta["description"]) if key == "home" else "",
        "content": body.strip(), "year": date.today().year,
    }
    return render(tpl, ctx)


def build_404(tpl, version):
    meta, body = read_page(ROOT / "content" / "404.html")
    body = expand(french_typography(body), "fr")
    s = STRINGS["fr"]
    nav = [f'      <a href="{url(k, "fr")}{f}"{" class=\"cta\"" if k == "contact" else ""}>{l}</a>' for l, k, f in s["nav"]]
    nav.append(f'      <a class="lang" href="{ROOT_PATH}/en/" hreflang="en" lang="en" title="English version">EN</a>')
    ctx = {
        **{k: v for k, v in s.items() if k.startswith("t_") or k in ("og_locale", "alt_name")},
        "lang": "fr", "title": esc(meta["title"]), "og_title": "Chaos Engineering",
        "description": esc(meta["description"]), "canonical": BASE + "/", "base": BASE, "root": ROOT_PATH,
        "alternates": '<meta name="robots" content="noindex">', "version": version, "page_class": "page-404",
        "home_url": ROOT_PATH + "/", "legal_url": url("legal", "fr"), "alt_url": ROOT_PATH + "/en/", "alt_lang": "en",
        "nav": "\n".join(nav),
        "footer_nav": "\n".join(f'        <li><a href="{url(k, "fr")}{f}">{l}</a></li>' for l, k, f in s["footer"]),
        "jsonld": "", "content": body.strip(), "year": date.today().year,
    }
    return render(tpl, ctx)


def redirect_page(target):
    return (f'<!doctype html><html lang="fr"><head><meta charset="utf-8">'
            f'<title>Chaos Engineering</title><meta name="robots" content="noindex">'
            f'<link rel="canonical" href="{BASE}{target}"><meta http-equiv="refresh" content="0; url={ROOT_PATH}{target}">'
            f'</head><body><p><a href="{ROOT_PATH}{target}">{BASE}{target}</a></p></body></html>\n')


def sitemap():
    today = date.today().isoformat()
    rows = []
    for key, paths in PAGES.items():
        for lang in ("fr", "en"):
            alts = "".join(f'<xhtml:link rel="alternate" hreflang="{lg}" href="{BASE}/{paths[lg]}"/>' for lg in ("fr", "en"))
            rows.append(f"  <url><loc>{BASE}/{paths[lang]}</loc><lastmod>{today}</lastmod>{alts}</url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            + "\n".join(rows) + "\n</urlset>\n")


def write(rel, text):
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


def check():
    """Placeholders, house style and internal links on the built site."""
    ids = {}
    pages = {}
    for f in OUT.rglob("*.html"):
        rel = f.relative_to(OUT).as_posix()
        html = f.read_text(encoding="utf-8")
        pages[rel] = html
        ids[rel] = set(re.findall(r'\sid="([^"]+)"', html))
    for rel, html in pages.items():
        visible = re.sub(r"<(script|style|svg)\b.*?</\1>", "", html, flags=re.S)
        n = visible.count('class="todo"')
        if n:
            warnings.append(f"{rel}: {n} placeholder(s) to complete")
        if "—" in visible:
            warnings.append(f"{rel}: em dash found")
        if re.search(r"\bmaison\b", re.sub(r"<[^>]+>", " ", visible), re.I):
            warnings.append(f"{rel}: the word 'maison' found")
        for href in re.findall(r'(?:href|src)="(/[^"/][^"]*|/)"', html):
            if ROOT_PATH:
                if not href.startswith(ROOT_PATH + "/"):
                    warnings.append(f"{rel}: link without {ROOT_PATH} prefix: {href}")
                    continue
                href = href[len(ROOT_PATH):]
            path, _, frag = href.partition("#")
            path = path.split("?")[0]
            target = (path.lstrip("/") + "index.html") if path.endswith("/") else path.lstrip("/")
            if not (OUT / target).exists():
                warnings.append(f"{rel}: broken link {href}")
            elif frag and target in ids and frag not in ids[target]:
                warnings.append(f"{rel}: missing anchor {href}")
        for frag in re.findall(r'href="#([^"]+)"', html):
            if frag not in ids[rel]:
                warnings.append(f"{rel}: missing anchor #{frag}")


def main():
    global ROOT_PATH
    release = "--release" in sys.argv
    if "--preview-path" in sys.argv:
        ROOT_PATH = "/" + sys.argv[sys.argv.index("--preview-path") + 1].strip("/")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "static", OUT)
    version = hashlib.sha1((ROOT / "static/css/site.css").read_bytes()).hexdigest()[:8]
    tpl = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    for key, paths in PAGES.items():
        for lang, path in paths.items():
            write(path + "index.html", build_page(tpl, key, lang, version))
    write("404.html", build_404(tpl, version))
    for old, new in REDIRECTS.items():
        write(old + "index.html", redirect_page(new))
    write("sitemap.xml", sitemap())
    write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n")
    if not ROOT_PATH:
        write("CNAME", DOMAIN + "\n")
    write(".nojekyll", "")
    check()
    n = sum(1 for _ in OUT.rglob("*.html"))
    print(f"built {n} pages into {OUT.relative_to(ROOT)}/" + (f" for {ROOT_PATH}/" if ROOT_PATH else ""))
    for w in warnings:
        print("WARNING:", w)
    if release and warnings:
        sys.exit("release blocked: fix the warnings above")


if __name__ == "__main__":
    main()
