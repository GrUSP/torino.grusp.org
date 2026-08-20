# torino.grusp.org

Sito del **Programmer User Group Torino** (PUG Torino) in [Jekyll](https://jekyllrb.com/),
pubblicato con GitHub Pages. Sostituisce il blog WordPress storico mantenendo
URL, contenuti e feed.

## Struttura

```
_config.yml            configurazione del sito (titolo, permalink, plugin)
_layouts/              default, home, post, page, archive
_includes/             head, header, footer, card articolo, meta, paginazione
_posts/                26 articoli importati da WordPress (AAAA-MM-GG-slug.md)
pagine/                pagine statiche (chi siamo, contatti, archivio)
assets/css/style.scss  tema, con i design token in cima al file
assets/img/            logo e banner — vedi assets/img/README.md
tools/                 script di export dal sito WordPress e di import in Jekyll
_import/               export WordPress originale (WXR) usato per la migrazione
.github/workflows/     build e deploy su GitHub Pages
```

## Sviluppo in locale

```bash
bundle install
bundle exec jekyll serve --livereload   # http://127.0.0.1:4000
```

## Dove è pubblicato

Su <https://torino.grusp.org> (dominio personalizzato nel file `CNAME`).
`url` e `baseurl` in `_config.yml` devono descrivere quell'indirizzo:
`baseurl` va lasciato vuoto, perché il sito sta sulla radice del dominio.

## Pubblicare

Ogni push su `main` fa partire il workflow *Build e deploy su GitHub Pages*
(`.github/workflows/jekyll.yml`), che compila il sito e lo pubblica.
Le pull request eseguono solo la build, senza deploy.

## URL mantenuti da WordPress

| WordPress | Jekyll |
| --- | --- |
| `/nome-articolo/` | identico (`permalink: /:title/`) |
| `/page/2/` | identico (`jekyll-paginate`) |
| `/category/conferenze/` | identico (`jekyll-archives`) |
| `/tag/php/` | identico (`jekyll-archives`) |
| `/chi-siamo/`, `/contatti/` | identici |
| `/mailing-list/` | redirect a `/contatti/` (mailing list dismessa) |
| `/AAAA/MM/nome-articolo/` (vecchi permalink) | redirect (`jekyll-redirect-from`) |
| `/feed/` | redirect verso `/feed.xml` (Atom, `jekyll-feed`) |

## Aggiornare i contenuti

Nuovo articolo: crea `_posts/AAAA-MM-GG-slug.md` con

```yaml
---
title: "Titolo dell'incontro"
date: 2026-09-15 19:00:00 +0200
categories: ["sessioni"]
tags: ["php", "torino"]
author: "Nome Cognome"
---
```

Per re-importare da WordPress vedi [MIGRAZIONE.md](MIGRAZIONE.md).
