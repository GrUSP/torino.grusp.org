#!/usr/bin/env python3
"""Importa i contenuti di un blog WordPress in questo sito Jekyll.

Due sorgenti possibili:

  1. Export ufficiale WordPress (WXR / "Strumenti -> Esporta -> Tutti i contenuti").
     È la sorgente da preferire: contiene *tutti* i post, le pagine, gli allegati,
     le categorie e i tag, senza i tagli di lunghezza tipici dei feed.

         python3 tools/import_wordpress.py --wxr _import/torino.wordpress.xml --download-media

  2. Feed RSS del sito (utile quando l'export non è disponibile). Il feed espone
     solo gli ultimi N articoli, quindi va usato come ripiego.

         python3 tools/import_wordpress.py --feed _import/feeds/feed.xml
         python3 tools/import_wordpress.py --feed https://torino.grusp.org/feed/

Genera `_posts/AAAA-MM-GG-slug.md` e `pagine/slug.md`, scarica opzionalmente i
media in `assets/uploads/` e riscrive i link ai media nel contenuto.

Solo libreria standard. Se `html2text` è installato viene usato per una
conversione HTML -> Markdown più accurata; altrimenti si usa un convertitore
minimale interno che lascia intatto l'HTML che non sa tradurre (kramdown lo
renderizza comunque correttamente).
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

NS = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "wp": "http://wordpress.org/export/1.2/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "excerpt": "http://wordpress.org/export/1.2/excerpt/",
}

USER_AGENT = "torino.grusp.org-jekyll-importer/1.0"


# --------------------------------------------------------------------------- #
# Utility
# --------------------------------------------------------------------------- #
def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = value.encode("ascii", "ignore").decode("ascii").lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "senza-titolo"


def local_timezone(name: str = "Europe/Rome"):
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:  # pragma: no cover - fallback per ambienti senza tzdata
        return timezone(timedelta(hours=1))


TZ = local_timezone()


def parse_wp_date(raw: str | None) -> datetime | None:
    if not raw or raw.startswith("0000"):
        return None
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ)
    except ValueError:
        return None


def parse_rfc822(raw: str | None) -> datetime | None:
    if not raw:
        return None
    from email.utils import parsedate_to_datetime

    try:
        dt = parsedate_to_datetime(raw.strip())
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ)


def yaml_scalar(value: str) -> str:
    """Serializza una stringa come scalare YAML sempre valido."""
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def yaml_list(values) -> str:
    return "[" + ", ".join(yaml_scalar(v) for v in values) + "]"


def text_of(node, path: str, default: str = "") -> str:
    found = node.find(path, NS)
    if found is None or found.text is None:
        return default
    return found.text


# --------------------------------------------------------------------------- #
# Conversione HTML -> Markdown
# --------------------------------------------------------------------------- #
def _minimal_html_to_markdown(source: str) -> str:
    text = source

    # Shortcode WordPress non traducibili: li rimuoviamo lasciando il contenuto.
    text = re.sub(r"\[/?(?:caption|gallery|embed|vc_[a-z_]+)[^\]]*\]", "", text)

    text = re.sub(r"<!--\s*more\s*-->", "\n<!--more-->\n", text, flags=re.I)

    for level in range(1, 7):
        text = re.sub(
            rf"<h{level}[^>]*>(.*?)</h{level}>",
            lambda m, lv=level: "\n" + "#" * lv + " " + m.group(1).strip() + "\n",
            text,
            flags=re.I | re.S,
        )

    text = re.sub(r"<(strong|b)[^>]*>(.*?)</\1>", r"**\2**", text, flags=re.I | re.S)
    text = re.sub(r"<(em|i)[^>]*>(.*?)</\1>", r"*\2*", text, flags=re.I | re.S)
    text = re.sub(
        r'<a[^>]*href=["\'](.*?)["\'][^>]*>(.*?)</a>', r"[\2](\1)", text, flags=re.I | re.S
    )
    text = re.sub(
        r'<img[^>]*?src=["\'](.*?)["\'][^>]*?alt=["\'](.*?)["\'][^>]*>', r"![\2](\1)", text, flags=re.I
    )
    text = re.sub(r'<img[^>]*?src=["\'](.*?)["\'][^>]*>', r"![](\1)", text, flags=re.I)

    text = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1", text, flags=re.I | re.S)
    text = re.sub(r"</?(?:ul|ol)[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<blockquote[^>]*>(.*?)</blockquote>", lambda m: "\n" + "\n".join(
        "> " + line for line in m.group(1).strip().splitlines()) + "\n", text, flags=re.I | re.S)
    text = re.sub(r"<hr[^>]*>", "\n---\n", text, flags=re.I)
    text = re.sub(r"<br\s*/?>", "  \n", text, flags=re.I)
    text = re.sub(r"</p>\s*<p[^>]*>", "\n\n", text, flags=re.I)
    text = re.sub(r"</?p[^>]*>", "\n\n", text, flags=re.I)
    text = re.sub(r"</?(?:span|div|font)[^>]*>", "", text, flags=re.I)

    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def html_to_markdown(source: str, keep_html: bool = False) -> str:
    source = (source or "").strip()
    if not source:
        return ""
    if keep_html:
        return source
    try:
        import html2text  # type: ignore

        converter = html2text.HTML2Text()
        converter.body_width = 0
        converter.unicode_snob = True
        converter.protect_links = True
        converter.wrap_links = False
        converter.inline_links = True
        return converter.handle(source).strip()
    except ImportError:
        return _minimal_html_to_markdown(source)


SHORTCODE_RE = re.compile(
    r"\[/?(?:caption|gallery|embed|contact-form[^\]]*|contact-field[^\]]*|vc_[a-z_]+)[^\]]*\]",
    re.I,
)
FORM_RE = re.compile(r"<form\b.*?</form>", re.I | re.S)


def strip_shortcodes(source: str) -> str:
    """Rimuove gli shortcode dei plugin WordPress, che su Jekyll non esistono."""
    return SHORTCODE_RE.sub("", source)


def protect_forms(source: str):
    """Mette da parte i <form> HTML: html2text li scarterebbe, ma su un sito
    statico restano validi (es. iscrizione alla mailing list su ml.grusp.org)."""
    forms: list[str] = []

    def stash(match: re.Match) -> str:
        forms.append(match.group(0))
        return f"\n\nJEKYLLFORMPLACEHOLDER{len(forms) - 1}\n\n"

    return FORM_RE.sub(stash, source), forms


def restore_forms(source: str, forms) -> str:
    for index, form in enumerate(forms):
        source = source.replace(f"JEKYLLFORMPLACEHOLDER{index}", form)
    return source


def wpautop(source: str) -> str:
    """WordPress salva i post senza <p>: ricostruiamo i paragrafi."""
    if re.search(r"<(p|div|ul|ol|h[1-6]|blockquote|pre|table|figure)\b", source, re.I):
        return source
    blocks = [b.strip() for b in re.split(r"\n\s*\n", source) if b.strip()]
    return "\n\n".join("<p>" + b.replace("\n", "<br />\n") + "</p>" for b in blocks)


# --------------------------------------------------------------------------- #
# Modello
# --------------------------------------------------------------------------- #
class Entry:
    def __init__(self, **kw):
        self.title: str = kw.get("title", "")
        self.slug: str = kw.get("slug", "")
        self.date: datetime | None = kw.get("date")
        self.content: str = kw.get("content", "")
        self.excerpt: str = kw.get("excerpt", "")
        self.author: str = kw.get("author", "")
        self.categories: list[str] = kw.get("categories", [])
        self.tags: list[str] = kw.get("tags", [])
        self.link: str = kw.get("link", "")
        self.kind: str = kw.get("kind", "post")  # post | page


# --------------------------------------------------------------------------- #
# Parsing WXR
# --------------------------------------------------------------------------- #
def parse_wxr(path_or_url: str, include_drafts: bool = False):
    raw = read_source(path_or_url)
    root = ET.fromstring(raw)
    channel = root.find("channel")
    if channel is None:
        raise SystemExit("File WXR non valido: manca <channel>.")

    # Mappa login -> nome visualizzato, per non ritrovarsi "admin" nei post.
    authors = {}
    for author in channel.findall("wp:author", NS):
        login = text_of(author, "wp:author_login")
        display = text_of(author, "wp:author_display_name") or login
        if login:
            authors[login] = display

    entries, attachments = [], []
    for item in channel.findall("item"):
        post_type = text_of(item, "wp:post_type")
        status = text_of(item, "wp:status")

        if post_type == "attachment":
            url = text_of(item, "wp:attachment_url")
            if url:
                attachments.append(url)
            continue
        if post_type not in ("post", "page"):
            continue
        if status != "publish" and not include_drafts:
            continue

        cats, tags = [], []
        for cat in item.findall("category"):
            domain = cat.get("domain")
            name = (cat.get("nicename") or cat.text or "").strip()
            if not name:
                continue
            if domain == "category":
                cats.append(name)
            elif domain == "post_tag":
                tags.append(name)

        content = text_of(item, "content:encoded")
        entries.append(
            Entry(
                title=html.unescape(text_of(item, "title")).strip(),
                slug=text_of(item, "wp:post_name") or slugify(text_of(item, "title")),
                date=parse_wp_date(text_of(item, "wp:post_date"))
                or parse_rfc822(text_of(item, "pubDate")),
                content=content,
                excerpt=text_of(item, "excerpt:encoded"),
                author=authors.get(
                    text_of(item, "dc:creator"), text_of(item, "dc:creator")
                ),
                categories=cats,
                tags=tags,
                link=text_of(item, "link"),
                kind="page" if post_type == "page" else "post",
            )
        )
    return entries, attachments


# --------------------------------------------------------------------------- #
# Parsing feed RSS
# --------------------------------------------------------------------------- #
def parse_feed(path_or_url: str):
    raw = read_source(path_or_url)
    root = ET.fromstring(raw)
    channel = root.find("channel")
    if channel is None:
        raise SystemExit("Feed non valido: manca <channel>. Atteso RSS 2.0.")

    entries = []
    for item in channel.findall("item"):
        link = text_of(item, "link")
        cats, tags = [], []
        for cat in item.findall("category"):
            name = (cat.get("nicename") or cat.text or "").strip()
            domain = (cat.get("domain") or "").lower()
            if not name:
                continue
            (tags if "tag" in domain else cats).append(name)

        content = text_of(item, "content:encoded") or text_of(item, "description")
        slug = ""
        if link:
            slug = urllib.parse.urlparse(link).path.strip("/").split("/")[-1]

        entries.append(
            Entry(
                title=html.unescape(text_of(item, "title")).strip(),
                slug=slug or slugify(text_of(item, "title")),
                date=parse_rfc822(text_of(item, "pubDate")),
                content=content,
                excerpt=text_of(item, "description"),
                author=text_of(item, "dc:creator"),
                categories=cats,
                tags=tags,
                link=link,
                kind="post",
            )
        )
    return entries


def read_source(path_or_url: str) -> bytes:
    if path_or_url == "-":
        return sys.stdin.buffer.read()
    if path_or_url.startswith(("http://", "https://")):
        req = urllib.request.Request(path_or_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    return Path(path_or_url).read_bytes()


# --------------------------------------------------------------------------- #
# Media
# --------------------------------------------------------------------------- #
UPLOAD_RE = re.compile(r"https?://[^\s\"'<>()]+/wp-content/uploads/[^\s\"'<>()]+", re.I)


def media_local_path(url: str, media_dir: Path) -> Path:
    path = urllib.parse.urlparse(url).path
    marker = "/wp-content/uploads/"
    rel = path.split(marker, 1)[1] if marker in path else os.path.basename(path)
    rel = urllib.parse.unquote(rel)
    return media_dir / rel


def download_media(urls, media_dir: Path, site_root: Path, dry_run: bool) -> int:
    downloaded = 0
    for url in sorted(set(urls)):
        target = media_local_path(url, media_dir)
        if target.exists():
            continue
        if dry_run:
            log(f"  [dry-run] scaricherei {url} -> {target.relative_to(site_root)}")
            downloaded += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp, open(target, "wb") as fh:
                fh.write(resp.read())
            downloaded += 1
            log(f"  media: {url} -> {target.relative_to(site_root)}")
        except Exception as exc:  # noqa: BLE001
            log(f"  ATTENZIONE: download fallito per {url}: {exc}")
    return downloaded


def rewrite_media_urls(text: str, media_url_prefix: str) -> str:
    def repl(match: re.Match) -> str:
        url = match.group(0)
        path = urllib.parse.urlparse(url).path
        rel = path.split("/wp-content/uploads/", 1)[1]
        return f"{media_url_prefix.rstrip('/')}/{rel}"

    return UPLOAD_RE.sub(repl, text)


# --------------------------------------------------------------------------- #
# Scrittura file Jekyll
# --------------------------------------------------------------------------- #
def render_front_matter(entry: Entry, args) -> str:
    lines = ["---"]
    lines.append(f"title: {yaml_scalar(entry.title)}")

    if entry.kind == "post":
        if entry.date:
            lines.append(f"date: {entry.date.strftime('%Y-%m-%d %H:%M:%S %z')}")
        if entry.categories:
            lines.append(f"categories: {yaml_list(entry.categories)}")
        if entry.tags:
            lines.append(f"tags: {yaml_list(entry.tags)}")
        if entry.author:
            lines.append(f"author: {yaml_scalar(entry.author)}")
    else:
        lines.append(f"permalink: /{entry.slug}/")

    if entry.excerpt.strip():
        excerpt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", entry.excerpt)).strip()
        if excerpt:
            lines.append(f"description: {yaml_scalar(excerpt[:300])}")

    if entry.link and args.keep_original_url:
        lines.append(f"original_url: {yaml_scalar(entry.link)}")

    redirects = []
    if entry.link and args.redirects:
        path = urllib.parse.urlparse(entry.link).path
        if path and path.strip("/") != entry.slug:
            redirects.append(path if path.endswith("/") else path + "/")
        if entry.date and entry.kind == "post":
            redirects.append(entry.date.strftime(f"/%Y/%m/{entry.slug}/"))
    redirects = [r for r in dict.fromkeys(redirects) if r.strip("/") != entry.slug]
    if redirects:
        lines.append(f"redirect_from: {yaml_list(redirects)}")

    lines.append("---")
    return "\n".join(lines)


def target_path(entry: Entry, site_root: Path, args_pages_dir: str = "pagine") -> Path:
    if entry.kind == "page":
        return site_root / args_pages_dir / f"{entry.slug}.md"
    date = entry.date or datetime.now(TZ)
    return site_root / "_posts" / f"{date.strftime('%Y-%m-%d')}-{entry.slug}.md"


def write_entry(entry: Entry, site_root: Path, args) -> tuple[Path, bool]:
    path = target_path(entry, site_root, args.pages_dir)
    body = strip_shortcodes(entry.content)
    body, forms = protect_forms(body)
    body = wpautop(body)
    if args.download_media or args.rewrite_media:
        body = rewrite_media_urls(body, args.media_url_prefix)
    body = html_to_markdown(body, keep_html=args.format == "html")
    body = restore_forms(body, forms)
    document = render_front_matter(entry, args) + "\n\n" + body + "\n"

    existed = path.exists()
    if existed and args.skip_existing:
        return path, False
    if not args.dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(document, encoding="utf-8")
    return path, True


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Importa un blog WordPress (export WXR o feed RSS) in Jekyll.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--wxr", help="File (o URL) dell'export WordPress WXR. '-' per stdin.")
    source.add_argument("--feed", action="append", help="File o URL di un feed RSS. Ripetibile.")

    parser.add_argument("--site-root", default=".", help="Radice del sito Jekyll (default: .)")
    parser.add_argument("--pages-dir", default="pagine",
                        help="Cartella delle pagine statiche (default: pagine)")
    parser.add_argument("--format", choices=["markdown", "html"], default="markdown",
                        help="Come salvare il corpo dei post (default: markdown)")
    parser.add_argument("--download-media", action="store_true",
                        help="Scarica i media da /wp-content/uploads/ e riscrive i link")
    parser.add_argument("--rewrite-media", action="store_true",
                        help="Riscrive i link ai media senza scaricarli")
    parser.add_argument("--media-dir", default="assets/uploads",
                        help="Cartella locale dei media (default: assets/uploads)")
    parser.add_argument("--media-url-prefix", default="/assets/uploads",
                        help="Prefisso URL dei media nel sito (default: /assets/uploads)")
    parser.add_argument("--include-drafts", action="store_true", help="Importa anche le bozze")
    parser.add_argument("--skip-slug", action="append", default=[], metavar="SLUG",
                        help="Non importa il contenuto con questo slug. Ripetibile. "
                             "Usa --skip-slug mailing-list: quella pagina e' stata "
                             "dismessa e la sua URL redirige su /contatti/.")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Non sovrascrive i file già presenti")
    parser.add_argument("--no-redirects", dest="redirects", action="store_false",
                        help="Non genera redirect_from dalle vecchie URL")
    parser.add_argument("--no-original-url", dest="keep_original_url", action="store_false",
                        help="Non salva original_url nel front matter")
    parser.add_argument("--limit", type=int, help="Importa al massimo N contenuti")
    parser.add_argument("--dry-run", action="store_true", help="Mostra cosa farebbe senza scrivere")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    site_root = Path(args.site_root).resolve()
    media_dir = site_root / args.media_dir

    attachments: list[str] = []
    if args.wxr:
        entries, attachments = parse_wxr(args.wxr, include_drafts=args.include_drafts)
    else:
        entries = []
        for feed in args.feed:
            entries.extend(parse_feed(feed))

    # Deduplica per (tipo, slug) tenendo la versione più recente.
    unique: dict[tuple[str, str], Entry] = {}
    for entry in entries:
        unique[(entry.kind, entry.slug)] = entry
    entries = sorted(unique.values(), key=lambda e: e.date or datetime.min.replace(tzinfo=TZ))

    if args.skip_slug:
        skipped = {s.strip("/") for s in args.skip_slug}
        entries = [e for e in entries if e.slug not in skipped]
        log(f"Esclusi per --skip-slug: {', '.join(sorted(skipped))}")

    if args.limit:
        entries = entries[-args.limit:]

    log(f"Trovati {len(entries)} contenuti da importare.")

    written = 0
    media_urls: list[str] = []
    for entry in entries:
        if not entry.title and not entry.content:
            continue
        media_urls.extend(UPLOAD_RE.findall(entry.content))
        path, did_write = write_entry(entry, site_root, args)
        written += 1 if did_write else 0
        flag = "" if did_write else " (saltato, già presente)"
        log(f"  {entry.kind}: {path.relative_to(site_root)}{flag}")

    if args.download_media:
        media_urls.extend(u for u in attachments if "/wp-content/uploads/" in u)
        log(f"Media referenziati: {len(set(media_urls))}")
        download_media(media_urls, media_dir, site_root, args.dry_run)

    log(f"Fatto: {written} file scritti{' (dry-run)' if args.dry_run else ''}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
