# Migrazione da WordPress a Jekyll / GitHub Pages

## Stato

| Attività | Stato |
| --- | --- |
| Repository Jekyll (`GrUSP/torino.grusp.org`) | fatto |
| Import di 26 articoli e 3 pagine dall'export WordPress | fatto |
| Categorie, tag, autori, paginazione, feed, redirect vecchi permalink | fatto |
| Workflow di build e deploy su GitHub Pages | fatto (nel repo) |
| Attivazione di GitHub Pages nelle impostazioni del repo | **da fare a mano** (serve un permesso admin) |
| Download dei media da `wp-content/uploads` | fatto (27 file su 30, recuperati da Internet Archive) |
| Logo e banner in `assets/img/` | **da caricare** (vedi `assets/img/README.md`) |
| Cambio DNS di `torino.grusp.org` verso GitHub Pages | fatto |

## 1. Attivare GitHub Pages

Repository → **Settings** → **Pages** → *Build and deployment* →
**Source: GitHub Actions**.

Poi lancia il workflow (Actions → *Build e deploy su GitHub Pages* → *Run workflow*,
oppure con il primo push su `main`). L'anteprima sarà su
`https://grusp.github.io/torino.grusp.org/`.

> L'API Pages non è raggiungibile dall'ambiente in cui è stata preparata la
> migrazione, quindi questo passaggio va fatto dall'interfaccia web.

## 2. Portare i media dentro al repository (fatto, con due buchi)

Gli articoli referenziavano immagini e slide su
`https://torino.grusp.org/wp-content/uploads/...`. Il DNS è già stato girato,
quindi quelle URL le serve GitHub Pages, che non le ha: erano 30 file (37
riferimenti) tutti in 404.

Il vecchio hosting non è più raggiungibile e non è saltato fuori un backup
degli upload, ma quasi tutti quei file sono su Internet Archive. Li recupera
`tools/fetch_wayback_media.py`, che li scarica in `assets/uploads/` con la
struttura `AAAA/MM/` e poi riscrive i link negli articoli:

```bash
python3 tools/fetch_wayback_media.py --dry-run   # cosa farebbe
python3 tools/fetch_wayback_media.py --rewrite   # scarica e riscrive i link
```

Lo script ricava l'elenco scandendo `_posts/` e `pagine/`, non da un file di
appoggio: resta valido anche quando la documentazione invecchia. Scarta le
catture illeggibili (pagine di errore servite con codice 200, PDF tronchi) e
riprova su snapshot più vecchi.

Risultato: **27 file su 30 recuperati**. Restano fuori le due foto del meetup
del 18 dicembre 2025, mai archiviate, più le slide Node.js di maggio 2025, che
sono state recuperate ma pesano 14 MB e per ora vivono su Internet Archive
invece che nel repository. Dettagli e cosa resta da fare a mano in
`_import/media-mancanti.txt`.

> **Non** usare `tools/import_wordpress.py --rewrite-media` per riscrivere i
> link: rigenera i post dall'export WXR e cancella le modifiche fatte a mano,
> a partire da `pagine/contatti.md`.

## 3. Logo e banner

Vedi `assets/img/README.md`: servono `head.png` (banner della hero-box) e
`logo_pugtorino.png` (logo quadrato per header, favicon e anteprime social).

## 4. Cambio DNS e dominio personalizzato

Il DNS è stato girato: il sito sta sulla radice di <https://torino.grusp.org>,
con il dominio nel file `CNAME` e in `_config.yml`:

```yaml
url: "https://torino.grusp.org"
baseurl: ""
```

Il tema usa ovunque `relative_url`, quindi i link seguono il `baseurl`.

> `baseurl: "/"` **non** è equivalente a `""`: produce link con doppia barra
> (`//assets/css/style.css`), che il browser risolve come un altro host, e il
> sito resta senza CSS. Lo smoke test in CI ora blocca questo caso.

Rimane da spuntare **Enforce HTTPS** in Settings → Pages, quando GitHub ha
completato la verifica del dominio, e da spegnere WordPress una volta
verificato che tutto risponda (vedi punto 2 sui media).

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
- [x] Immagini degli articoli servite da `assets/uploads/` (tranne le due foto
      del 18 dicembre 2025, vedi `_import/media-mancanti.txt`)
- [ ] Redirect da `/mailing-list/` a `/contatti/` (la mailing list e' stata dismessa)
- [ ] `sitemap.xml` e `robots.txt` (generati da `jekyll-sitemap`)

## Script disponibili

| Script | A cosa serve |
| --- | --- |
| `tools/export_wordpress_feeds.sh` | Scarica feed RSS/Atom, API REST e sitemap del sito WordPress in `_import/` |
| `tools/fetch_assets.sh` | Scarica logo, favicon e immagini della home in `assets/img/originali/` |
| `tools/import_wordpress.py` | Converte l'export WXR (o i feed) in post e pagine Jekyll, con media e redirect |
| `tools/fetch_wayback_media.py` | Recupera da Internet Archive i media di `wp-content/uploads` e riscrive i link negli articoli |

`tools/import_wordpress.py --help` elenca tutte le opzioni
(`--dry-run`, `--format html`, `--include-drafts`, `--limit`, ...).
