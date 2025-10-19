# Portfolio di Progetti Python di Tommaso Biscottini

Questa è una collezione curata dei miei migliori progetti personali, realizzati per dimostrare le mie competenze in Data Engineering, automazione di processi e integrazione di API.

---

### 1. End-to-End Data Pipeline & Grocery Optimizer
*Progetto completo all'interno della cartella: [`esselunga-grocery-optimizer`](./esselunga-grocery-optimizer)*

Una pipeline di dati completa che estrae, pulisce e analizza oltre 17.000 prodotti dal sito di Esselunga. Il progetto culmina con l'implementazione di un modello di **Programmazione Lineare (PuLP)** per trovare il paniere alimentare a costo minimo che rispetta complessi vincoli nutrizionali.

**Tecnologie:** Python, Pandas, Selenium, PuLP, concurrent.futures.

---

### 2. AI-Powered PDF-to-Anki Card Generator
*File: [`pdf_to_anki_with_gemini.py`](./pdf_to_anki_with_gemini.py)*

Uno strumento di automazione che legge un file PDF, invia il testo all'**API di Google Gemini** per una sintesi intelligente e la creazione di domande, e infine aggiunge le flashcard generate automaticamente all'applicazione Anki tramite **AnkiConnect**.

**Tecnologie:** Python, Google Gemini API, PyMuPDF, AnkiConnect.

---

### 3. Advanced Web Scraper for Dynamic Websites
*File: [`playwright_scrape_justwatch_infinite_scroll.py`](./playwright_scrape_justwatch_infinite_scroll.py)*

Uno scraper avanzato che utilizza **Playwright** per estrarre dati da siti web dinamici che caricano contenuti tramite scroll infinito, ottimizzato per la velocità bloccando il caricamento di risorse non necessarie.

**Tecnologie:** Python, Playwright, asyncio.
