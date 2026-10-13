"""Generate the hero band: a Voronoi foam that orders into a honeycomb.

Seeds sit on a triangular lattice; their random displacement decays from
left to right, so the Voronoi tessellation goes from a disordered foam to a
regular hexagonal honeycomb. Output: templates/partials/lattice.svg (inlined
by build.py), static/img/og.jpg (social preview) and the favicons.

Usage: python tools/lattice.py
"""
from pathlib import Path

import numpy as np
from scipy.spatial import Voronoi

ROOT = Path(__file__).resolve().parents[1]
W, H = 1600, 300
S = 30.0          # lattice spacing (distance between seeds)
SEED = 7


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def seeds(w, h, s, rng):
    dy = s * np.sqrt(3) / 2
    pts = []
    for j in range(-3, int(h / dy) + 4):
        off = 0.5 * s if j % 2 else 0.0
        for i in range(-3, int(w / s) + 4):
            pts.append((i * s + off, j * dy))
    pts = np.array(pts)
    # disorder: full on the left third, none on the right third
    amp = 0.62 * s * smoothstep((0.72 - pts[:, 0] / w) / 0.5)
    pts = pts + rng.uniform(-1, 1, pts.shape) * amp[:, None]
    # thin the seeds in the most disordered part so cell sizes vary
    drop = rng.random(len(pts)) < 0.28 * smoothstep((0.35 - pts[:, 0] / w) / 0.35)
    return pts[~drop]


def clip(p, q, w, h):
    """Liang-Barsky clipping of segment pq to [0,w]x[0,h]."""
    (x0, y0), (x1, y1) = p, q
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for pk, qk in ((-dx, x0), (dx, w - x0), (-dy, y0), (dy, h - y0)):
        if pk == 0:
            if qk < 0:
                return None
            continue
        r = qk / pk
        if pk < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return None
    return (x0 + t0 * dx, y0 + t0 * dy), (x0 + t1 * dx, y0 + t1 * dy)


def segments(w, h, s, seed):
    rng = np.random.default_rng(seed)
    vor = Voronoi(seeds(w, h, s, rng))
    out = []
    for a, b in vor.ridge_vertices:
        if a < 0 or b < 0:
            continue
        c = clip(vor.vertices[a], vor.vertices[b], w, h)
        if c and np.hypot(c[1][0] - c[0][0], c[1][1] - c[0][1]) > 0.5:
            out.append(c)
    return out


def write_svg(segs):
    d = "".join(f"M{p[0]:.1f} {p[1]:.1f}L{q[0]:.1f} {q[1]:.1f}" for p, q in segs)
    svg = (
        f'<svg class="lattice" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice" '
        'aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg">'
        '<defs><linearGradient id="lg" x1="0" x2="1" y1="0" y2="0">'
        '<stop offset="0" stop-color="var(--lattice-a)"/>'
        '<stop offset="1" stop-color="var(--lattice-b)"/></linearGradient></defs>'
        f'<path d="{d}" fill="none" stroke="url(#lg)" stroke-width="1.4" '
        'vector-effect="non-scaling-stroke" stroke-linecap="round"/></svg>\n'
    )
    out = ROOT / "templates" / "partials" / "lattice.svg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    print(f"{out.relative_to(ROOT)}: {len(segs)} segments, {len(svg) / 1024:.1f} kB")


def write_og():
    from PIL import Image, ImageDraw, ImageFont

    w, h, k = 1200, 630, 2  # supersampled
    img = Image.new("RGB", (w * k, h * k), (12, 20, 19))
    dr = ImageDraw.Draw(img)
    a, b = np.array((31, 168, 160)), np.array((170, 226, 72))
    for p, q in segments(w, h, 34.0, SEED):
        t = ((p[0] + q[0]) / 2) / w
        col = tuple(int(v) for v in (a + (b - a) * t) * 0.55 + np.array((12, 20, 19)) * 0.45)
        dr.line([(p[0] * k, p[1] * k), (q[0] * k, q[1] * k)], fill=col, width=2 * k)
    # text panel
    dr.rectangle([0, 170 * k, w * k, 460 * k], fill=(12, 20, 19))
    fonts = Path("C:/Windows/Fonts")
    try:
        big = ImageFont.truetype(str(ROOT / "static/fonts/space-grotesk.woff2"), 84 * k)
        big.set_variation_by_axes([600])
    except Exception:
        big = ImageFont.truetype(str(fonts / "segoeuib.ttf"), 84 * k)
    small = ImageFont.truetype(str(fonts / "segoeui.ttf"), 36 * k)
    logo = Image.open(ROOT / "static/img/logo-512.png").convert("RGBA").resize((150 * k, 150 * k), Image.LANCZOS)
    img.paste(logo, (80 * k, 240 * k), logo)
    dr.text((260 * k, 238 * k), "Chaos Engineering", font=big, fill=(240, 244, 242))
    dr.text((262 * k, 350 * k), "Expertise scientifique au service de l\u2019innovation", font=small, fill=(176, 196, 192))
    img = img.resize((w, h), Image.LANCZOS)
    out = ROOT / "static" / "img" / "og.jpg"
    img.save(out, quality=86, optimize=True, progressive=True)
    print(f"{out.relative_to(ROOT)}: {out.stat().st_size / 1024:.0f} kB")


def write_icons():
    from PIL import Image

    logo = Image.open(ROOT / "static/img/logo-512.png").convert("RGBA")
    logo.resize((32, 32), Image.LANCZOS).save(ROOT / "static/img/favicon-32.png", optimize=True)
    touch = Image.new("RGBA", (180, 180), (255, 255, 255, 255))
    inner = logo.resize((150, 150), Image.LANCZOS)
    touch.paste(inner, (15, 15), inner)
    touch.convert("RGB").save(ROOT / "static/img/apple-touch-icon.png", optimize=True)
    logo.save(ROOT / "static/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    logo.resize((96, 96), Image.LANCZOS).save(ROOT / "static/img/logo-96.png", optimize=True)


if __name__ == "__main__":
    write_svg(segments(W, H, S, SEED))
    write_og()
    write_icons()
