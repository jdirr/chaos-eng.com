"""Monthly health check of https://chaos-eng.com (standard library only).

Checks every page and asset of the sitemap, the redirects from the old
WordPress URLs, the TLS certificate, DNS (GitHub Pages A records, mail
forwarding MX), the copyright year and the age of the content.
Prints one line per problem and a summary; exit code 1 if anything fails.

Usage: python tools/healthcheck.py
"""
import re
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = "chaos-eng.com"
BASE = f"https://{HOST}"
GITHUB_A = {"185.199.108.153", "185.199.109.153", "185.199.110.153", "185.199.111.153"}
problems, notes = [], []


def fetch(url, follow=True):
    req = urllib.request.Request(url, headers={"User-Agent": "chaos-eng-healthcheck"})
    opener = urllib.request.build_opener() if follow else urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "replace"), r.headers
    except urllib.error.HTTPError as e:
        return e.code, "", e.headers
    except Exception as e:  # network, TLS
        return None, str(e), {}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def check_pages():
    status, xml, _ = fetch(f"{BASE}/sitemap.xml")
    if status != 200:
        problems.append(f"sitemap.xml: HTTP {status} {xml[:120]}")
        return
    urls = re.findall(r"<loc>([^<]+)</loc>", xml)
    assets = set()
    for u in urls:
        s, html, _ = fetch(u)
        if s != 200:
            problems.append(f"{u}: HTTP {s}")
            continue
        if 'class="todo"' in html:
            problems.append(f"{u}: placeholder left on the page")
        if 'name="robots" content="noindex"' in html:
            problems.append(f"{u}: page marked noindex (provisional build deployed?)")
        y = re.search(r"&copy; (\d{4})", html)
        if y and int(y.group(1)) != datetime.now().year:
            problems.append(f"{u}: footer year {y.group(1)}, rebuild needed")
        assets.update(re.findall(r'(?:href|src)="(/(?:css|img|fonts)/[^"?]+)', html))
    for a in sorted(assets):
        s, _, _ = fetch(BASE + a)
        if s != 200:
            problems.append(f"{a}: HTTP {s}")
    notes.append(f"{len(urls)} pages, {len(assets)} assets checked")
    for old in ("/about/", "/contactez-nous/"):
        s, html, _ = fetch(BASE + old)
        if s != 200 or "http-equiv=\"refresh\"" not in html:
            problems.append(f"redirect {old}: HTTP {s}, refresh missing")
    s, _, _ = fetch(f"https://www.{HOST}/", follow=False)
    if s not in (301, 302, 308):
        problems.append(f"www.{HOST}: expected a redirect, got HTTP {s}")
    s, _, h = fetch(f"http://{HOST}/", follow=False)
    if s not in (301, 308) or not str(h.get("Location", "")).startswith("https://"):
        problems.append(f"http://{HOST}: not redirected to HTTPS (HTTP {s})")


def check_tls():
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((HOST, 443), timeout=15) as sock:
            with ctx.wrap_socket(sock, server_hostname=HOST) as tls:
                cert = tls.getpeercert()
    except Exception as e:
        problems.append(f"TLS: {e}")
        return
    end = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    days = (end - datetime.now(timezone.utc)).days
    issuer = dict(x[0] for x in cert["issuer"]).get("organizationName", "?")
    notes.append(f"certificate {issuer}, {days} days left")
    if days < 14:
        problems.append(f"TLS certificate expires in {days} days")


def nslookup(*args):
    out = subprocess.run(["nslookup", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20).stdout
    return out


def check_dns():
    out = nslookup(HOST, "8.8.8.8")
    tail = out.split(HOST, 1)[-1]
    a = set(re.findall(r"\b\d+\.\d+\.\d+\.\d+\b", tail))
    if not a or not a <= GITHUB_A:
        problems.append(f"DNS A records {sorted(a)} differ from GitHub Pages")
    mx = nslookup("-type=MX", HOST, "8.8.8.8")
    if "smtp-fwd.wordpress.com" not in mx:
        problems.append("MX smtp-fwd.wordpress.com missing: contact@ forwarding broken")


def check_content_age():
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%cs", "--", "content"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20).stdout.strip()
    except Exception:
        return
    if out:
        age = (datetime.now() - datetime.fromisoformat(out)).days
        notes.append(f"content last changed {out} ({age} days)")
        if age > 180:
            problems.append(f"content unchanged for {age} days: review references, projects, news")


def main():
    for f in (check_pages, check_tls, check_dns, check_content_age):
        try:
            f()
        except Exception as e:
            problems.append(f"{f.__name__} crashed: {e!r}")
    print(f"chaos-eng.com health check, {datetime.now():%Y-%m-%d %H:%M}")
    for n in notes:
        print("  ok:", n)
    for p in problems:
        print("  PROBLEM:", p)
    print("  all good" if not problems else f"  {len(problems)} problem(s)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
