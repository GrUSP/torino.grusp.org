#!/usr/bin/env bash
# Esporta feed, API REST e sitemap del blog WordPress in _import/.
#
#   ./tools/export_wordpress_feeds.sh                      # usa https://torino.grusp.org
#   BASE_URL=https://esempio.it ./tools/export_wordpress_feeds.sh
#
# L'export completo (WXR) va comunque scaricato a mano da
# WordPress -> Strumenti -> Esporta -> Tutti i contenuti, e salvato in
# _import/torino.wordpress.xml : è l'unica sorgente che contiene TUTTI i post.
set -euo pipefail

BASE_URL="${BASE_URL:-https://torino.grusp.org}"
OUT_DIR="${OUT_DIR:-_import}"
FEED_DIR="$OUT_DIR/feeds"
API_DIR="$OUT_DIR/api"
UA="torino.grusp.org-jekyll-migration/1.0"

mkdir -p "$FEED_DIR" "$API_DIR"

fetch() { # fetch <url> <file di destinazione>
  local url="$1" dest="$2"
  if curl -fsSL --max-time 60 -A "$UA" "$url" -o "$dest"; then
    printf '  ok   %-58s -> %s\n' "$url" "$dest"
  else
    printf '  SKIP %-58s (non disponibile)\n' "$url"
    rm -f "$dest"
    return 1
  fi
}

echo "== Feed principali =="
fetch "$BASE_URL/feed/"                 "$FEED_DIR/feed.rss.xml"     || true
fetch "$BASE_URL/feed/atom/"            "$FEED_DIR/feed.atom.xml"    || true
fetch "$BASE_URL/comments/feed/"        "$FEED_DIR/comments.rss.xml" || true

echo "== Feed paginato (tutti gli articoli) =="
page=1
while :; do
  dest="$FEED_DIR/feed.page-$page.xml"
  fetch "$BASE_URL/feed/?paged=$page" "$dest" || break
  if ! grep -q "<item" "$dest"; then
    rm -f "$dest"
    break
  fi
  page=$((page + 1))
  [ "$page" -gt 50 ] && break
done
echo "  pagine di feed scaricate: $((page - 1))"

echo "== API REST WordPress (contenuto completo, senza troncamenti) =="
for resource in posts pages categories tags media users; do
  page=1
  while :; do
    dest="$API_DIR/$resource.page-$page.json"
    fetch "$BASE_URL/wp-json/wp/v2/$resource?per_page=100&page=$page" "$dest" || break
    # Una pagina vuota (`[]`) chiude la paginazione.
    if [ "$(tr -d ' \n' < "$dest")" = "[]" ]; then
      rm -f "$dest"
      break
    fi
    page=$((page + 1))
    [ "$page" -gt 50 ] && break
  done
done

echo "== Sitemap =="
for sm in sitemap.xml sitemap_index.xml wp-sitemap.xml; do
  fetch "$BASE_URL/$sm" "$OUT_DIR/$sm" || true
done

echo
echo "Export completato in $OUT_DIR/."
echo "Passo successivo: python3 tools/import_wordpress.py --wxr $OUT_DIR/torino.wordpress.xml --download-media"
