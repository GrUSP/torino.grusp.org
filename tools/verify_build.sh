#!/usr/bin/env bash
# Smoke test del sito generato: verifica che le URL storiche di WordPress
# esistano ancora in _site/. Usato dalla CI dopo `jekyll build`.
set -uo pipefail

SITE="${SITE:-_site}"
fail=0

check() { # check <percorso relativo a _site> <descrizione>
  if [ -e "$SITE/$1" ]; then
    printf '  ok   %-56s %s\n' "$1" "$2"
  else
    printf '  FAIL %-56s %s\n' "$1" "$2"
    fail=1
  fi
}

echo "== Pagine principali =="
check "index.html"                 "home"
check "page/2/index.html"          "paginazione"
check "404.html"                   "pagina di errore"
check "archivio/index.html"        "archivio"

echo "== Pagine statiche ereditate da WordPress =="
check "chi-siamo/index.html"       "/chi-siamo/"
check "contatti/index.html"        "/contatti/"
check "mailing-list/index.html"    "redirect da /mailing-list/ (pagina dismessa)"

echo "== Articoli e archivi =="
check "e-nato-il-pug-torino/index.html"                    "primo articolo (2011)"
check "auguri-di-natale-con-php-8-5/index.html"            "ultimo articolo (2025)"
check "category/conferenze/index.html"                     "categoria"
check "category/comunicazioni/index.html"                  "categoria"
check "tag/php-to-start/index.html"                        "tag"

echo "== Feed, sitemap e redirect =="
check "feed.xml"                   "feed Atom"
check "feed/index.html"            "redirect dal vecchio /feed/"
check "sitemap.xml"                "sitemap"
check "robots.txt"                 "robots"
check "2015/04/php-7-e-architetture-middleware/index.html" "vecchio permalink datato"

if grep -q '/contatti/' "$SITE/mailing-list/index.html" 2>/dev/null; then
  echo "  ok   /mailing-list/ redirige verso /contatti/"
else
  echo "  FAIL /mailing-list/ non redirige verso /contatti/"
  fail=1
fi

echo "== Conteggi =="
posts=$(find "$SITE" -name index.html -path "*/*" | wc -l)
expected_posts=$(find _posts -name '*.md' | wc -l)
generated_posts=0
for f in _posts/*.md; do
  slug="$(basename "$f" .md)"
  slug="${slug#????-??-??-}"
  [ -e "$SITE/$slug/index.html" ] && generated_posts=$((generated_posts + 1))
done
printf '  articoli attesi: %s, generati: %s (pagine HTML totali: %s)\n' \
  "$expected_posts" "$generated_posts" "$posts"
if [ "$generated_posts" -ne "$expected_posts" ]; then
  echo "  FAIL: alcuni articoli non sono stati generati"
  fail=1
fi

# Nessun residuo di shortcode WordPress nell'HTML pubblicato.
if grep -rlE '\[(contact-form|caption|gallery)\b' "$SITE" --include='*.html' >/dev/null 2>&1; then
  echo "  FAIL: shortcode WordPress residui nel sito generato"
  grep -rlE '\[(contact-form|caption|gallery)\b' "$SITE" --include='*.html' | head
  fail=1
else
  echo "  ok   nessuno shortcode WordPress residuo"
fi

exit "$fail"
