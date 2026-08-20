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
check "assets/img/head.png"        "banner della hero-box"

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

echo "== Dominio, baseurl e asset =="
BASEURL="${BASEURL:-$(sed -n 's/^baseurl: *"\(.*\)"/\1/p' _config.yml)}"
SITE_URL="$(sed -n 's/^url: *"\(.*\)"/\1/p' _config.yml)"

# baseurl: "/" non e' equivalente a "": genera //assets/... , che il browser
# risolve come host esterno. Deve essere vuoto o iniziare (e non finire) con /.
case "$BASEURL" in
  "")  echo "  ok   baseurl vuoto: il sito sta sulla radice del dominio" ;;
  */)  echo "  FAIL baseurl \"$BASEURL\" termina con '/': genera link con doppia barra"; fail=1 ;;
  /*)  echo "  ok   baseurl \"$BASEURL\"" ;;
  *)   echo "  FAIL baseurl \"$BASEURL\" non inizia con '/'"; fail=1 ;;
esac

# Link protocol-relative: sintomo classico di un baseurl sbagliato.
if grep -qE '(href|src)="//' "$SITE/index.html"; then
  echo "  FAIL la home contiene link protocol-relative (//...), quasi sempre un baseurl errato"
  grep -oE '(href|src)="//[^"]*"' "$SITE/index.html" | sort -u | head
  fail=1
else
  echo "  ok   nessun link protocol-relative nella home"
fi

# Dominio personalizzato: il CNAME deve finire nel sito e combaciare con url.
if [ -f "$SITE/CNAME" ]; then
  cname="$(tr -d ' \n\r' < "$SITE/CNAME")"
  host="${SITE_URL#https://}"; host="${host#http://}"; host="${host%%/*}"
  if [ "$cname" = "$host" ]; then
    echo "  ok   CNAME ($cname) coerente con url in _config.yml"
  else
    echo "  FAIL CNAME ($cname) diverso dall'host di url ($host): canonical, feed e sitemap punterebbero altrove"
    fail=1
  fi
else
  echo "  ok   nessun CNAME (sito senza dominio personalizzato)"
fi
expected_css="${BASEURL}/assets/css/style.css"
if grep -q "href=\"$expected_css\"" "$SITE/index.html"; then
  echo "  ok   la home linka il CSS su $expected_css"
else
  echo "  FAIL la home non linka il CSS su $expected_css"
  grep -o 'href="[^"]*style.css"' "$SITE/index.html" || echo "  (nessun link al foglio di stile)"
  fail=1
fi
check "assets/css/style.css"       "foglio di stile generato"

echo "== Campione di HTML generato =="
grep -oE '<link rel="stylesheet"[^>]*>' "$SITE/index.html" | head -1 | sed 's/^/  /'
grep -oE '<link rel="canonical"[^>]*>' "$SITE/index.html" | head -1 | sed 's/^/  /'
grep -oE '<link rel="alternate"[^>]*>' "$SITE/index.html" | head -1 | sed 's/^/  /'

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

# I media non ancora importati restano su wp-content: dopo il cambio DNS
# quelle URL non esistono piu'. Segnalato, non bloccante.
leftover=$(grep -rho 'https://[a-z.]*/wp-content/uploads/[^"'"'"' )]*' "$SITE" --include='*.html' | sort -u | wc -l)
if [ "$leftover" -gt 0 ]; then
  echo "  ATTENZIONE: $leftover media ancora referenziati su wp-content/uploads (vedi MIGRAZIONE.md punto 2)"
else
  echo "  ok   nessun media referenziato su wp-content"
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
