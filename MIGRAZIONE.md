# Migrazione da WordPress a Jekyll / GitHub Pages

## Stato

| Attività | Stato |
| --- | --- |
| Repository Jekyll (`GrUSP/torino.grusp.org`) | fatto |
| Import di 26 articoli e 3 pagine dall'export WordPress | fatto |
| Categorie, tag, autori, paginazione, feed, redirect vecchi permalink | fatto |
| Workflow di build e deploy su GitHub Pages | fatto (nel repo) |
| Attivazione di GitHub Pages nelle impostazioni del repo | **da fare a mano** (serve un permesso admin) |
| Download dei media da `wp-content/uploads` | **da fare** (rete bloccata durante la migrazione) |
| Logo e banner in `assets/img/` | **da caricare** (vedi `assets/img/README.md`) |
| Cambio DNS di `torino.grusp.org` verso GitHub Pages | **da fare per ultimo** |

## 1. Attivare GitHub Pages

Repository → **Settings** → **Pages** → *Build and deployment* →
**Source: GitHub Actions**.

Poi lancia il workflow (Actions → *Build e deploy su GitHub Pages* → *Run workflow*,
oppure con il primo push su `main`). L'anteprima sarà su
`https://grusp.github.io/torino.grusp.org/`.

> L'API Pages non è raggiungibile dall'ambiente in cui è stata preparata la
> migrazione, quindi questo passaggio va fatto dall'interfaccia web.

## 2. Portare i media dentro al repository

Gli articoli referenziano ancora le immagini su
`https://torino.grusp.org/wp-content/uploads/...`: finché WordPress è online
funzionano, ma **smettono di funzionare quando il DNS punta a GitHub Pages**.
Prima del cambio DNS, da una macchina con accesso al sito:

```bash
python3 tools/import_wordpress.py \
  --wxr _import/torino.wordpress.xml \
  --download-media \
  --skip-existing \
  --skip-slug mailing-list
```

`--skip-existing` non tocca le pagine modificate a mano (es. `pagine/contatti.md`);
`--skip-slug mailing-list` evita di ricreare la pagina della mailing list, che è
stata dismessa e la cui URL ora redirige su `/contatti/`.

Lo script scarica i file in `assets/uploads/` (stessa struttura `AAAA/MM/`) e
riscrive i link nei post. Poi commit e push.

Nota: `--skip-existing` non riscrive i post già presenti. Per rigenerarli con i
link locali togli l'opzione (e ricontrolla `pagine/contatti.md`, che è scritta
a mano perché il form Jetpack non esiste più).

## 3. Logo e banner

Vedi `assets/img/README.md`: servono `head.png` (banner della hero-box) e
`logo_pugtorino.png` (logo quadrato per header, favicon e anteprime social).

## 4. Cambio DNS e dominio personalizzato

Finché il DNS non è girato il sito vive sull'anteprima di progetto
<https://grusp.github.io/torino.grusp.org/>, e `_config.yml` la descrive:

```yaml
url: "https://grusp.github.io"
baseurl: "/torino.grusp.org"
```

Il tema usa ovunque `relative_url`, quindi i link seguono il `baseurl`.

Al cambio DNS, nell'ordine:

1. In `_config.yml`: `url: "https://torino.grusp.org"` e `baseurl: ""`
   (senza questo passaggio il sito sul dominio finale cerca gli asset sotto
   `/torino.grusp.org/`).
2. Crea il file `CNAME` nella root del repository con dentro `torino.grusp.org`
   (oppure imposta *Custom domain* in Settings → Pages: GitHub lo crea da solo).
3. Sul DNS di `grusp.org` fai puntare `torino` a `grusp.github.io` (record CNAME).
4. Attendi la verifica del dominio e spunta **Enforce HTTPS**.
5. Spegni il WordPress solo dopo aver verificato che il sito statico risponda.

## Sorgente di GitHub Pages

Pages deve stare su **Source: GitHub Actions**. Se viene impostata su *Deploy
from a branch*, il builder classico compila il sito in parallelo a questo
workflow ignorando `jekyll-archives` (niente pagine di categoria e tag): le due
pubblicazioni si sovrascrivono a vicenda. Il workflow prova a riportare la
sorgente su GitHub Actions a ogni run e, se non ci riesce, lo segnala come
warning.

> Non aggiungere `CNAME` prima del passo 2: GitHub Pages inizierebbe a
> redirigere l'anteprima `github.io` verso un dominio ancora servito da WordPress.

## 5. Verifiche prima dello spegnimento di WordPress

- [ ] Home, paginazione (`/page/2/`), archivio, pagine statiche
- [ ] Categorie (`/category/conferenze/`) e tag (`/tag/php/`)
- [ ] Un vecchio permalink datato, es. `/2015/04/php-7-e-architetture-middleware/`
- [ ] Feed su `/feed.xml` e redirect da `/feed/`
- [ ] Immagini degli articoli servite da `assets/uploads/`
- [ ] Redirect da `/mailing-list/` a `/contatti/` (la mailing list e' stata dismessa)
- [ ] `sitemap.xml` e `robots.txt` (generati da `jekyll-sitemap`)

## Script disponibili

| Script | A cosa serve |
| --- | --- |
| `tools/export_wordpress_feeds.sh` | Scarica feed RSS/Atom, API REST e sitemap del sito WordPress in `_import/` |
| `tools/fetch_assets.sh` | Scarica logo, favicon e immagini della home in `assets/img/originali/` |
| `tools/import_wordpress.py` | Converte l'export WXR (o i feed) in post e pagine Jekyll, con media e redirect |

`tools/import_wordpress.py --help` elenca tutte le opzioni
(`--dry-run`, `--format html`, `--include-drafts`, `--limit`, ...).
