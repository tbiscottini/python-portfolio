# Portfolio di Progetti Python di Tommaso Biscottini

Questa è una collezione curata dei miei migliori script personali, realizzati per dimostrare le mie competenze pratiche in web scraping, automazione di processi e integrazione di API.

---

### 1. Advanced Web Scraper for Infinite-Scroll Websites
*File: `playwright_scrape_justwatch_infinite_scroll.py`*

Uno scraper avanzato che utilizza **Playwright** per estrarre dati da siti web dinamici che caricano contenuti tramite scroll infinito. È ottimizzato per la velocità, bloccando il caricamento di risorse non necessarie (CSS, immagini).

**Tecnologie:** Python, Playwright, asyncio.

---

### 2. Game Pass Data Analysis Pipeline
*File: `gamepass_picker.py`*

Uno script che automatizza la raccolta di dati di videogiochi, superando le protezioni anti-bot con **Cloudscraper**. Utilizza il **multithreading** per parallelizzare le richieste e **Pandas** per la pulizia e l'analisi finale dei dati.

**Tecnologie:** Python, Pandas, Cloudscraper, BeautifulSoup, concurrent.futures.

---

### 3. AI-Powered PDF-to-Anki Card Generator
*File: `pdf_to_anki_with_gemini.py`*

Uno strumento di automazione che legge un file PDF, invia il testo all'**API di Google Gemini** per una sintesi intelligente e la creazione di domande "cloze", e infine aggiunge le flashcard generate automaticamente all'applicazione Anki tramite **AnkiConnect**.

**Tecnologie:** Python, Google Gemini API, PyMuPDF, AnkiConnect.
