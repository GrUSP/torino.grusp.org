#!/usr/bin/env bash
# Scarica i principali asset grafici del sito WordPress (logo, favicon,
# immagini di intestazione, og:image) in assets/img/originali/.
#
#   ./tools/fetch_assets.sh
#   BASE_URL=https://esempio.it ./tools/fetch_assets.sh
set -euo pipefail

BASE_URL="${BASE_URL:-https://torino.grusp.org}"
DEST="${DEST:-assets/img/originali}"
TMP="$(mktemp -d)"
UA="torino.grusp.org-jekyll-migration/1.0"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$DEST"

echo "Scarico la home di $BASE_URL ..."
curl -fsSL --max-time 60 -A "$UA" "$BASE_URL/" -o "$TMP/home.html"

# Estrae gli URL degli asset: favicon, logo, og:image, immagini in uploads.
{
  grep -oiE '<link[^>]+rel="[^"]*icon[^"]*"[^>]+href="[^"]+"' "$TMP/home.html" |
    grep -oiE 'href="[^"]+"' | cut -d'"' -f2
  grep -oiE '<meta[^>]+property="og:image"[^>]+content="[^"]+"' "$TMP/home.html" |
    grep -oiE 'content="[^"]+"' | cut -d'"' -f2
  grep -oiE 'src="[^"]+\.(png|jpe?g|svg|gif|webp)"' "$TMP/home.html" | cut -d'"' -f2
  grep -oiE "url\((['\"]?)[^)]+\.(png|jpe?g|svg|gif|webp)\1\)" "$TMP/home.html" |
    sed -E "s/^url\(['\"]?//; s/['\"]?\)$//"
} | sort -u > "$TMP/assets.txt"

count=0
while read -r url; do
  [ -z "$url" ] && continue
  case "$url" in
    //*)  url="https:$url" ;;
    /*)   url="$BASE_URL$url" ;;
    http*) ;;
    *)    url="$BASE_URL/$url" ;;
  esac
  name="$(basename "${url%%\?*}")"
  if curl -fsSL --max-time 60 -A "$UA" "$url" -o "$DEST/$name"; then
    printf '  ok   %s\n' "$name"
    count=$((count + 1))
  else
    printf '  SKIP %s\n' "$url"
    rm -f "$DEST/$name"
  fi
done < "$TMP/assets.txt"

echo
echo "$count asset salvati in $DEST/."
echo "Scegli il logo definitivo e copialo in assets/img/logo.svg (o aggiorna 'logo:' in _config.yml)."
