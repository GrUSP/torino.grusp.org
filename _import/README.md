# Materiale di origine della migrazione

- `torino.wordpress.xml` — export WXR di WordPress 7.0.4 del 20/08/2026
  (26 articoli, 3 pagine, 56 allegati, categorie, tag e autori). È la sorgente
  usata per generare `_posts/` e `pagine/` con `tools/import_wordpress.py`.

I feed RSS/Atom del sito originale **non** sono stati scaricati durante la
migrazione: l'ambiente usato per prepararla ha l'accesso di rete a
`torino.grusp.org` bloccato dal proxy di egress (403 sulla CONNECT). Non è una
perdita di dati, perché il WXR contiene più informazioni del feed (che espone
solo gli ultimi N articoli). Per archiviarli comunque, da una rete senza
restrizioni:

```bash
./tools/export_wordpress_feeds.sh      # feed RSS/Atom, API REST wp-json, sitemap
```

Il nuovo feed del sito Jekyll è servito su `/feed.xml`, con redirect dal
vecchio `/feed/`.
