# Asset grafici da caricare

Questi file **non** sono nel repository: vanno caricati qui (drag & drop su
GitHub, oppure `git add`) con **esattamente questi nomi**, perché il tema li
referenzia in `_config.yml`.

| File da caricare in `assets/img/` | A cosa serve | Origine su WordPress |
| --- | --- | --- |
| `head.png` | Banner della hero-box in home (Mole + tastiera + wordmark) | <https://torino.grusp.org/wp-content/uploads/2025/03/cropped-head.png> |
| `logo_pugtorino.png` | Logo quadrato: header, favicon, anteprime social | <https://torino.grusp.org/wp-content/uploads/2020/01/logo_pugtorino.png> |

Se preferisci prenderli automaticamente, da una rete senza restrizioni:

```bash
curl -fsSL https://torino.grusp.org/wp-content/uploads/2025/03/cropped-head.png -o assets/img/head.png
curl -fsSL https://torino.grusp.org/wp-content/uploads/2020/01/logo_pugtorino.png -o assets/img/logo_pugtorino.png
```

oppure `./tools/fetch_assets.sh`, che scarica tutti gli asset referenziati
dalla home in `assets/img/originali/`.

> Nota: questi due file non hanno potuto essere scaricati durante la
> migrazione perché il dominio `torino.grusp.org` è bloccato dal proxy di rete
> dell'ambiente in cui è stato preparato il sito.
