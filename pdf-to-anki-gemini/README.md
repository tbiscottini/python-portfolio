# AI-Powered PDF-to-Anki Card Generator

Script di automazione che legge un PDF, invia il testo all'**API di Google Gemini** per ottenere una spiegazione semplificata e delle domande in formato cloze, e aggiunge automaticamente le flashcard generate al mazzo Anki desiderato tramite **AnkiConnect**.

## Come funziona
1. Estrae i paragrafi di testo dal PDF con `pdfplumber`.
2. Per ogni paragrafo, chiede a Gemini una spiegazione semplice e la trasforma in una flashcard con cancellazioni cloze multiple (`{{c1::...}}`, `{{c2::...}}`, ecc.).
3. Invia le note generate ad Anki tramite le API locali di AnkiConnect (`http://localhost:8765`).

## Prerequisiti
- Anki desktop installato con il plugin [AnkiConnect](https://ankiweb.net/shared/info/2055492159)
- Una API key di Google Gemini ([Google AI Studio](https://makersuite.google.com/app/apikey))
- `pip install google-generativeai pdfplumber requests`

## Configurazione ed esecuzione
Prima di eseguire lo script, apri `pdf_to_anki_with_gemini.py` e imposta `GOOGLE_API_KEY` e, se necessario, `ANKI_DECK_NAME`. Poi lancia:

```bash
python pdf_to_anki_with_gemini.py
```

Lo script chiederà a runtime il percorso del file PDF da processare.

**Tecnologie:** Python, Google Gemini API, PyMuPDF/pdfplumber, AnkiConnect.
