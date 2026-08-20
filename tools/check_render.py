#!/usr/bin/env python3
"""Controlla che ogni pagina del sito generato sia renderizzata correttamente.

Verifica, su tutti gli HTML in `_site/`:

- niente Liquid non processato ({{ ... }} o {% ... %}) finito nell'output;
- ogni pagina ha <title>, intestazione, contenuto e piè di pagina;
- i link interni puntano a qualcosa che esiste davvero nel sito generato;
- quante immagini sono locali e quante ancora remote (i media su
  `wp-content/uploads` non esistono più dopo il cambio DNS).

Esce con 1 se trova pagine vuote, Liquid non processato o link interni rotti.
Uso: python3 tools/check_render.py [cartella-del-sito]
"""

from __future__ import annotations

import html
import re
import sys
import urllib.parse
from collections import Counter
from pathlib import Path

TAG_RE = re.compile(r"<(script|style)\b.*?</\1>|<[^>]+>", re.S | re.I)
LIQUID_RE = re.compile(r"{{[^}]*}}|{%[^%]*%}")
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
REFRESH_RE = re.compile(r'http-equiv=["\']refresh["\']', re.I)
HREF_RE = re.compile(r'href=["\']([^"\'#]+)["\']', re.I)
IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)

MIN_TEXT = 200  # caratteri di testo sotto i quali la pagina è sospetta


def visible_text(markup: str) -> str:
    body = markup.split("<body", 1)[-1]
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", body))).strip()


def resolve(link: str, site: Path) -> Path | None:
    """Percorso atteso nel sito generato per un link interno, o None se esterno."""
    if link.startswith(("http://", "https://", "//", "mailto:", "tel:", "data:", "javascript:")):
        return None
    path = urllib.parse.unquote(link.split("?", 1)[0].split("#", 1)[0])
    if not path.startswith("/"):
        return None  # link relativo: raro nel tema, non lo valutiamo
    target = site / path.lstrip("/")
    return target / "index.html" if path.endswith("/") else target


def main(argv: list[str]) -> int:
    site = Path(argv[1] if len(argv) > 1 else "_site")
    if not site.is_dir():
        print(f"Cartella non trovata: {site}")
        return 1

    pages = sorted(site.rglob("*.html"))
    empty, liquid, missing_parts = [], [], []
    broken: list[tuple[str, str]] = []
    img_hosts: Counter[str] = Counter()
    local_imgs = 0
    redirects = 0

    for page in pages:
        rel = page.relative_to(site).as_posix()
        markup = page.read_text(encoding="utf-8", errors="replace")

        if LIQUID_RE.search(markup):
            liquid.append(rel)

        if REFRESH_RE.search(markup):
            redirects += 1
        else:
            text = visible_text(markup)
            if len(text) < MIN_TEXT:
                empty.append((rel, len(text)))
            parts = []
            if not TITLE_RE.search(markup):
                parts.append("title")
            if "site-header" not in markup:
                parts.append("header")
            if "site-footer" not in markup:
                parts.append("footer")
            if "<main" not in markup:
                parts.append("main")
            if parts:
                missing_parts.append((rel, ",".join(parts)))

        for link in HREF_RE.findall(markup):
            target = resolve(link, site)
            if target is not None and not target.exists():
                broken.append((rel, link))

        for src in IMG_RE.findall(markup):
            if src.startswith(("http://", "https://", "//")):
                img_hosts[urllib.parse.urlparse(src if "//" != src[:2] else "https:" + src).netloc] += 1
            else:
                local_imgs += 1

    print(f"Pagine HTML analizzate: {len(pages)} (di cui {redirects} pagine di redirect)")
    print(f"Immagini locali: {local_imgs}")
    for host, count in img_hosts.most_common():
        print(f"Immagini remote su {host}: {count}")

    if liquid:
        print(f"\nERRORE — Liquid non processato in {len(liquid)} pagine:")
        for rel in liquid[:10]:
            print(f"  {rel}")

    if empty:
        print(f"\nERRORE — {len(empty)} pagine praticamente vuote (< {MIN_TEXT} caratteri):")
        for rel, size in empty[:10]:
            print(f"  {rel} ({size} caratteri)")

    if missing_parts:
        print(f"\nERRORE — {len(missing_parts)} pagine senza elementi di layout:")
        for rel, parts in missing_parts[:10]:
            print(f"  {rel}: manca {parts}")

    if broken:
        unique = sorted({link for _, link in broken})
        print(f"\nERRORE — {len(broken)} link interni rotti ({len(unique)} destinazioni):")
        for link in unique[:15]:
            source = next(src for src, dst in broken if dst == link)
            print(f"  {link}  (es. da {source})")

    problems = bool(liquid or empty or missing_parts or broken)
    print("\nEsito:", "PROBLEMI RILEVATI" if problems else "tutte le pagine sono renderizzate correttamente")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
