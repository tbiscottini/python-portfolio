# Advanced Web Scraper for Dynamic Websites (JustWatch)

Scraper avanzato basato su **Playwright** per estrarre titoli di film da [JustWatch](https://www.justwatch.com/it/film), un sito che carica i contenuti tramite scroll infinito. Ottimizzato per la velocità: blocca il caricamento di immagini, CSS e font non necessari e si ferma automaticamente quando non compaiono più nuovi elementi dopo una serie di scroll consecutivi.

## Come funziona
1. Apre la pagina target con Playwright (Chromium) e, se configurati, inietta i cookie di sessione.
2. Esegue scroll ripetuti attendendo il caricamento della rete (`networkidle`), raccogliendo i titoli man mano che appaiono.
3. Si ferma quando raggiunge il limite configurato (`MAX_TITLES_TO_SCRAPE`) o dopo `MAX_STABLE_SCROLLS` scroll senza nuovi risultati.

## Prerequisiti
- `pip install playwright`
- `playwright install` (per scaricare i browser necessari)

## Configurazione ed esecuzione
Le impostazioni principali (URL target, timeout, limite titoli, modalità headless, cookie di sessione) sono all'inizio di `playwright_scrape_justwatch_infinite_scroll.py`. Aggiorna i valori placeholder in `YOUR_COOKIES` se il sito richiede una sessione autenticata, poi esegui:

```bash
python playwright_scrape_justwatch_infinite_scroll.py
```

**Tecnologie:** Python, Playwright, asyncio.
