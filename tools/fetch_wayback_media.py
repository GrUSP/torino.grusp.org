#!/usr/bin/env python3
"""Recupera da Internet Archive i media WordPress che il sito non serve più.

Gli articoli importati referenziano immagini e slide su
`https://torino.grusp.org/wp-content/uploads/...`. Dopo il cambio DNS quelle
URL le serve GitHub Pages, che quei file non li ha: sono tutte 404. Il vecchio
hosting non è più raggiungibile, ma quasi tutti i file hanno uno snapshot su
Wayback Machine.

L'elenco delle URL da recuperare viene ricavato **scandendo i sorgenti**
(`_posts/`, `pagine/`) invece di leggere `_import/media-mancanti.txt`: così lo
script resta valido anche quando quel file invecchia, e riflette sempre ciò che
è davvero scritto negli articoli.

Per ogni URL si cerca uno snapshot e lo si scarica usando il suffisso `id_` nel
timestamp (`https://web.archive.org/web/20250804072022id_/https://...`), che
restituisce il file originale e non la versione riscritta da Wayback.

La ricerca dello snapshot usa la **CDX API**
(`https://web.archive.org/cdx/search/cdx`) e non la Availability API
(`https://archive.org/wayback/available`): la seconda risponde 429 dopo poche
richieste consecutive e renderebbe lo script inutilizzabile su trenta file. La
CDX ha il vantaggio di poter filtrare gli snapshot con `statuscode:200`, così
non si scarica la cattura di una pagina 404. Se anche la CDX non risponde si
ripiega sul redirect diretto `https://web.archive.org/web/2id_/<url>`, che
Wayback risolve da sé sullo snapshot più vicino.

Uso tipico:

    python3 tools/fetch_wayback_media.py --dry-run   # cosa farebbe
    python3 tools/fetch_wayback_media.py             # scarica in assets/uploads/
    python3 tools/fetch_wayback_media.py --rewrite   # riscrive i link nei sorgenti

Solo libreria standard, come gli altri script in `tools/`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "torino.grusp.org-jekyll-importer/1.0"
CDX_API = "https://web.archive.org/cdx/search/cdx"
# `2id_`: Wayback interpreta il timestamp incompleto e redirige da sé sullo
# snapshot più vicino, restituendo il file originale.
DIRECT_SNAPSHOT = "https://web.archive.org/web/2id_/"
RETRY_STATUS = (429, 500, 502, 503, 504)
SNAPSHOTS = 6  # quanti snapshot provare per URL prima di arrendersi
UPLOAD_RE = re.compile(r"https?://[^\s\"'<>()]+/wp-content/uploads/[^\s\"'<>()]+", re.I)
UPLOAD_MARKER = "/wp-content/uploads/"

# Directory dei sorgenti da scandire e, con --rewrite, da riscrivere.
SOURCE_DIRS = ("_posts", "pagine")
SOURCE_GLOB = "*.md"

# Firma attesa in testa al file, per estensione. Wayback a volte risponde 200
# con una pagina HTML di errore: senza questo controllo finirebbe nel repo.
MAGIC = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".pdf": (b"%PDF",),
}


def log(message: str) -> None:
    print(message, flush=True)


def site_host(root: Path) -> str:
    """Dominio del sito: dal CNAME se c'è, altrimenti da `url` in _config.yml."""
    cname = root / "CNAME"
    if cname.exists():
        return cname.read_text(encoding="utf-8").strip()
    config = root / "_config.yml"
    if config.exists():
        found = re.search(r'^url:\s*"(.*)"', config.read_text(encoding="utf-8"), re.M)
        if found:
            return urllib.parse.urlparse(found.group(1)).netloc
    return ""


def source_files(root: Path):
    for name in SOURCE_DIRS:
        directory = root / name
        if directory.is_dir():
            yield from sorted(directory.glob(SOURCE_GLOB))


def collect_urls(root: Path, host: str) -> dict[str, list[Path]]:
    """URL dei media -> file sorgente che le usano.

    Con `host` valorizzato si tiene solo ciò che stava sul nostro dominio: gli
    articoli linkano anche upload di siti terzi (banner di conferenze), che non
    sono roba nostra e non vanno copiati in `assets/uploads/`.
    """
    found: dict[str, list[Path]] = {}
    for path in source_files(root):
        for url in UPLOAD_RE.findall(path.read_text(encoding="utf-8")):
            if host and urllib.parse.urlparse(url).netloc != host:
                continue
            found.setdefault(url, []).append(path)
    return dict(sorted(found.items()))


def relative_media_path(url: str) -> str:
    """`2011/06/pug_torino.jpg` a partire dall'URL completa."""
    path = urllib.parse.urlparse(url).path
    rel = path.split(UPLOAD_MARKER, 1)[1] if UPLOAD_MARKER in path else path.lstrip("/")
    return urllib.parse.unquote(rel)


class TransientError(Exception):
    """Internet Archive ha risposto male ma potrebbe rispondere bene dopo."""


def fetch(url: str, timeout: int = 60, retries: int = 4, delay: float = 1.0) -> bytes:
    """GET con backoff sugli errori temporanei di Internet Archive.

    Il 429 è la norma quando si chiedono decine di file di fila: va ritentato,
    non scambiato per "questo file non esiste".
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    wait = max(delay, 1.0)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRY_STATUS:
                raise
            if attempt == retries - 1:
                raise TransientError(f"HTTP {exc.code} dopo {retries} tentativi") from exc
            log(f"    HTTP {exc.code}, riprovo fra {wait:.0f}s")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt == retries - 1:
                raise TransientError(str(exc)) from exc
            log(f"    errore di rete ({exc}), riprovo fra {wait:.0f}s")
        time.sleep(wait)
        wait *= 2
    raise TransientError("tentativi esauriti")


def snapshot_urls(url: str, delay: float, limit: int = SNAPSHOTS) -> list[str]:
    """Snapshot con esito 200 in forma `id_`, dal più recente al più vecchio.

    Ne restituisce più di uno di proposito: la cattura più recente non è
    necessariamente la migliore. Su questo sito le ultime catture di due PDF
    sono tronche, mentre quelle di qualche anno prima sono integre; provandole
    in ordine, il controllo di sanità scarta le tronche e tiene la prima buona.

    Lista vuota se la CDX non conosce l'URL. Solleva TransientError se non è
    riuscita a rispondere: chi chiama deve distinguere "non archiviato" da
    "non lo so".
    """
    query = urllib.parse.urlencode(
        {
            "url": url.split("://", 1)[1] if "://" in url else url,
            "output": "json",
            "filter": "statuscode:200",
            "fl": "timestamp,original",
            "collapse": "digest",
        }
    )
    raw = fetch(f"{CDX_API}?{query}", delay=delay)
    try:
        rows = json.loads(raw or b"[]")
    except json.JSONDecodeError as exc:
        raise TransientError(f"risposta CDX illeggibile: {exc}") from exc
    snapshots = [
        f"https://web.archive.org/web/{row[0]}id_/{row[1]}"
        for row in reversed(rows[1:])  # rows[0] è l'intestazione
    ]
    return snapshots[:limit]


def looks_sane(data: bytes, target: Path) -> str | None:
    """None se il contenuto è plausibile, altrimenti il motivo dello scarto."""
    if not data:
        return "file vuoto"
    suffix = target.suffix.lower()
    expected = MAGIC.get(suffix)
    if expected and not data.startswith(expected):
        head = data[:64].lstrip().lower()
        if head.startswith((b"<!doctype", b"<html")):
            return "risposta HTML invece del file"
        return f"firma non coerente con {suffix} ({data[:8]!r})"
    # Il solo magic number non basta: Wayback consegna certe catture troncate a
    # un multiplo tondo (1 MiB, 5 MiB), con l'intestazione intatta e la coda
    # mancante. Un PDF integro finisce con %%EOF.
    if suffix == ".pdf" and b"%%EOF" not in data[-4096:]:
        return f"PDF troncato ({len(data)} byte, manca %%EOF)"
    return None


def candidate_snapshots(url: str, delay: float) -> list[str]:
    """Snapshot da provare, in ordine: prima la CDX, poi il redirect diretto."""
    candidates: list[str] = []
    try:
        candidates.extend(snapshot_urls(url, delay))
    except TransientError as exc:
        log(f"  CDX non raggiungibile per {url}: {exc}")
    candidates.append(DIRECT_SNAPSHOT + url)
    return candidates


def download(url: str, target: Path, delay: float) -> bool:
    for archived in candidate_snapshots(url, delay):
        time.sleep(delay)
        try:
            data = fetch(archived, delay=delay)
        except urllib.error.HTTPError as exc:
            log(f"  {url}: HTTP {exc.code} su {archived}")
            continue
        except TransientError as exc:
            log(f"  ATTENZIONE: download fallito da {archived}: {exc}")
            continue
        problem = looks_sane(data, target)
        if problem:
            log(f"  ATTENZIONE: scartato {archived}: {problem}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        log(f"  scaricato: {url} -> {target} ({len(data)} byte)")
        return True
    log(f"  non recuperato: {url}")
    return False


def rewrite_sources(
    root: Path, media_dir: Path, url_prefix: str, host: str, dry_run: bool
) -> int:
    """Sostituisce le URL wp-content con quelle locali, solo per i file presenti.

    I riferimenti ai media che non siamo riusciti a recuperare restano intatti:
    vanno gestiti a mano, non nascosti.
    """
    changed = 0
    for path in source_files(root):
        text = path.read_text(encoding="utf-8")

        def replace(match: re.Match) -> str:
            url = match.group(0)
            if host and urllib.parse.urlparse(url).netloc != host:
                return url
            rel = relative_media_path(url)
            if not (media_dir / rel).exists():
                return url
            return f"{url_prefix.rstrip('/')}/{rel}"

        updated = UPLOAD_RE.sub(replace, text)
        if updated == text:
            continue
        changed += 1
        if dry_run:
            log(f"  [dry-run] riscriverei {path.relative_to(root)}")
            continue
        path.write_text(updated, encoding="utf-8")
        log(f"  riscritto: {path.relative_to(root)}")
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scarica da Wayback Machine i media WordPress mancanti."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="radice del sito Jekyll (default: cartella corrente)",
    )
    parser.add_argument(
        "--media-dir",
        type=Path,
        default=None,
        help="cartella di destinazione (default: <root>/assets/uploads)",
    )
    parser.add_argument(
        "--url-prefix",
        default="/assets/uploads",
        help="prefisso delle URL locali usato da --rewrite (default: /assets/uploads)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="considera solo i media di questo dominio "
        "(default: quello del sito; stringa vuota per non filtrare)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="pausa in secondi fra le richieste a Internet Archive (default: 1)",
    )
    parser.add_argument(
        "--force", action="store_true", help="riscarica anche i file già presenti"
    )
    parser.add_argument(
        "--rewrite",
        action="store_true",
        help="dopo il download riscrive i link nei sorgenti verso assets/uploads",
    )
    parser.add_argument(
        "--rewrite-only",
        action="store_true",
        help="salta il download e riscrive soltanto i link",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="mostra cosa farebbe senza scrivere"
    )
    args = parser.parse_args(argv)

    root: Path = args.root
    media_dir: Path = args.media_dir or root / "assets" / "uploads"
    host = site_host(root) if args.host is None else args.host

    urls = collect_urls(root, host)
    if not urls:
        log("Nessun riferimento a wp-content/uploads nei sorgenti: niente da fare.")
        return 0

    downloaded: list[str] = []
    skipped: list[str] = []
    unavailable: list[str] = []

    if not args.rewrite_only:
        log(f"{len(urls)} media referenziati nei sorgenti.")
        for url in urls:
            target = media_dir / relative_media_path(url)
            if target.exists() and not args.force:
                skipped.append(url)
                continue
            if args.dry_run:
                log(f"  [dry-run] scaricherei {url} -> {target}")
                downloaded.append(url)
                continue
            if download(url, target, args.delay):
                downloaded.append(url)
            else:
                unavailable.append(url)

        log("")
        log("Riepilogo:")
        log(f"  scaricati:      {len(downloaded)}")
        log(f"  già presenti:   {len(skipped)}")
        log(f"  non recuperati: {len(unavailable)}")
        for url in unavailable:
            log(f"    - {url} (usato in: "
                f"{', '.join(sorted({p.name for p in urls[url]}))})")

    if args.rewrite or args.rewrite_only:
        log("")
        log("Riscrittura dei link nei sorgenti:")
        changed = rewrite_sources(root, media_dir, args.url_prefix, host, args.dry_run)
        log(f"  file modificati: {changed}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
