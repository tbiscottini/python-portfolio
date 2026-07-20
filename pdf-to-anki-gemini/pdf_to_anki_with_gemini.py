import os
import time
import requests  # For talking to AnkiConnect
import google.generativeai as genai  # For talking to Gemini
import pdfplumber  # For reading PDFs
import re  # For fixing cloze format with regular expressions

# --- CONFIGURATION (IMPORTANT: Fill these out!) ---
# 1. Get your API key from Google AI Studio: https://makersuite.google.com/app/apikey
GOOGLE_API_KEY = "PUT YOUR KEY HERE"

# 2. Configure Gemini Model
# gemini-1.5-flash-latest is a great, fast choice for this task.
GEMINI_MODEL_NAME = "gemini-2.5-flash-preview-04-17"

# 3. Anki Configuration
ANKI_DECK_NAME = "University Studies"  # The deck you want to add cards to
ANKI_MODEL_NAME = "Cloze"  # Standard Anki Cloze model
ANKICONNECT_URL = "http://localhost:8765"  # Default for AnkiConnect

# 4. Prompts for Gemini (IN ITALIAN)
PROMPT_EXPLAIN_LIKE_12 = """
Spiega il seguente testo come se avessi 12 anni.
Sii chiaro, conciso e usa un linguaggio semplice. Concentrati sui concetti fondamentali.
Non aggiungere alcuna frase di circostanza, solo la spiegazione.
RISPONDI ESCLUSIVAMENTE IN ITALIANO.

Testo da spiegare:
---
{text_content}
---
Spiegazione Semplificata (in italiano):
"""

# --- THIS IS THE KEY CHANGE ---
# This new prompt instructs the AI to create MULTIPLE cloze deletions in one go.
PROMPT_CREATE_MULTIPLE_CLOZE = """
Basandoti sulla seguente spiegazione, crea un'unica frase per una flashcard Anki contenente *molteplici* cancellazioni cloze.
Il tuo obiettivo è trasformare tutti i concetti chiave, le parole importanti, le date o i nomi in cancellazioni cloze.
Il formato DEVE usare cancellazioni cloze numerate in sequenza: {{c1::testo}}, {{c2::testo}}, {{c3::testo}}, ecc. Per esempio: "La {{c1::veloce volpe marrone}} salta sopra il {{c2::cane pigro}}."
Mantieni il resto della frase come contesto.
RISPONDI ESCLUSIVAMENTE IN ITALIANO.
Produci solo la frase finale con le cancellazioni cloze. Non aggiungere alcun testo esplicativo extra, titoli o frasi di circostanza.

Testo da trasformare in cloze (in italiano):
---
{explained_text}
---
Output con Cancellazioni Cloze Multiple (in italiano):
"""

# --- Initialize Gemini ---
try:
    # Use a secret manager in production, but for a personal script, os.environ is fine.
    # GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY or GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY_HERE":
        print("ERROR: GOOGLE_API_KEY is not set. Please edit the script and add your key.")
        exit()
    genai.configure(api_key=GOOGLE_API_KEY)
    gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
except Exception as e:
    print(f"Error initializing Gemini: {e}")
    print("Please ensure your GOOGLE_API_KEY is set correctly.")
    exit()


# --- Helper Functions ---

def extract_paragraphs_from_pdf(pdf_path):
    """
    Like a robot that opens a PDF book and reads out paragraphs.
    It's smart enough to try and guess where a paragraph ends.
    """
    paragraphs = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            for page_num, page in enumerate(pdf.pages):
                print(f"Reading page {page_num + 1}...")
                page_text = page.extract_text(x_tolerance=2, y_tolerance=5)
                if page_text:
                    full_text += page_text + "\n"

            # A more robust way to split paragraphs
            # Split by two or more newlines, and filter out short/empty lines
            raw_paragraphs = re.split(r'\n\s*\n', full_text)
            paragraphs = [p.strip().replace('\n', ' ') for p in raw_paragraphs if p.strip() and len(p.split()) > 10]

        print(f"Extracted {len(paragraphs)} potential paragraphs from PDF.")
        return paragraphs
    except Exception as e:
        print(f"Error reading PDF '{pdf_path}': {e}")
        return []


def correct_cloze_format(text):
    """
    This little helper robot checks if the cloze format is {c1::text}
    and changes it to the correct {{c1::text}} format for Anki.
    It works for c1, c2, c10, etc.
    """
    pattern = r'{c(\d+)::(.*?)}'
    replacement = r'{{c\1::\2}}'
    corrected_text, num_replacements = re.subn(pattern, replacement, text)

    if num_replacements > 0:
        print(
            f"    Corrected cloze format from single to double braces. Corrected {num_replacements} instances.")
    return corrected_text


def ask_gemini(prompt_template, text_input, is_cloze_request=False):
    """
    Like sending a note to our super-smart Gemini helper and getting a reply.
    If it's a cloze request, it will also try to fix the cloze formatting.
    """
    prompt_data = {'text_content': text_input, 'explained_text': text_input}
    full_prompt = prompt_template.format_map(prompt_data)

    print(f"  Asking Gemini (using {GEMINI_MODEL_NAME})...")
    try:
        generation_config = genai.types.GenerationConfig(
            temperature=0.4,  # Slightly more creative for finding multiple good clozes
        )
        response = gemini_model.generate_content(
            full_prompt,
            generation_config=generation_config,
        )

        if response.parts:
            result_text = response.text.strip()
            if is_cloze_request:
                result_text = correct_cloze_format(result_text)
            return result_text
        elif response.prompt_feedback and response.prompt_feedback.block_reason:
            print(f"    Gemini response blocked. Reason: {response.prompt_feedback.block_reason}")
            if response.prompt_feedback.safety_ratings:
                for rating in response.prompt_feedback.safety_ratings:
                    print(f"      Safety Category: {rating.category}, Probability: {rating.probability}")
            return None
        else:
            print("    Gemini returned an empty response.")
            return None

    except Exception as e:
        print(f"    Error communicating with Gemini: {e}")
        if "rate limit" in str(e).lower() or "429" in str(e) or "503" in str(e) or "unavailable" in str(e).lower():
            print("    Rate limit or server error suspected. Waiting 60 seconds before retry...")
            time.sleep(60)
            # You can add a retry here if you want, for simplicity we'll just return None on error
        return None


def anki_connect_request(action, **params):
    """
    A helper to talk to the AnkiConnect bridge.
    """
    payload = {"action": action, "version": 6, "params": params}
    try:
        response = requests.post(ANKICONNECT_URL, json=payload, timeout=30)
        response.raise_for_status()
        response_json = response.json()
        if response_json.get("error"):
            print(f"  AnkiConnect Error: {response_json['error']}")
            return None
        return response_json["result"]
    except requests.exceptions.ConnectionError:
        print(f"  Error: Could not connect to AnkiConnect at {ANKICONNECT_URL}.")
        print("  Please ensure Anki is running and AnkiConnect add-on is installed and enabled.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  AnkiConnect Request Error: {e}")
        return None


# Use a global var to pass the filename for tagging without complex parameter drilling
pdf_file_path_for_tagging = ""


def create_anki_notes_payload(cards_data):
    """
    Prepares a list of notes in the format AnkiConnect expects for batch adding.
    """
    notes = []
    # Generate a base tag from the PDF filename
    pdf_filename_tag = ""
    if pdf_file_path_for_tagging:
        base_name = os.path.basename(pdf_file_path_for_tagging)
        pdf_filename_tag = os.path.splitext(base_name)[0].replace(" ", "_").replace("-", "_").lower()

    for i, (cloze_text, explanation_text) in enumerate(cards_data):
        if not cloze_text or not re.search(r"\{\{c\d+::.*?\}\}", cloze_text):
            print(f"  Skipping card {i + 1} due to invalid or missing cloze pattern: '{cloze_text}'")
            continue

        tags_for_note = ["automated_gemini", f"source_{pdf_filename_tag}"]

        note = {
            "deckName": ANKI_DECK_NAME,
            "modelName": ANKI_MODEL_NAME,
            "fields": {
                "Text": cloze_text,
                "Extra": explanation_text
            },
            "options": {
                "allowDuplicate": False,
                "duplicateScope": "deck",
                "duplicateScopeOptions": {
                    "deckName": ANKI_DECK_NAME,
                    "checkChildren": False
                }
            },
            "tags": tags_for_note
        }
        notes.append(note)
    return notes


# --- Main Workflow ---
def main():
    global pdf_file_path_for_tagging  # To use it in create_anki_notes_payload for tagging
    print("Starting PDF to Anki Card Automation Script (Italian Multi-Cloze Output)!")

    pdf_file_path_input = input("Enter the path to your PDF file: ").strip().replace('"', '')
    if not os.path.exists(pdf_file_path_input):
        print(f"Error: PDF file not found at '{pdf_file_path_input}'")
        return

    # Set the global variable for tagging
    pdf_file_path_for_tagging = pdf_file_path_input

    # --- Configuration for testing: Number of paragraphs to process ---
    # Set to a small number (e.g., 3) for testing, or a large number (e.g., 9999) to process the whole PDF.
    TEST_LIMIT_NUM_PARAGRAPHS = 5
    # --- End of test configuration ---

    print("\nChecking Anki connection...")
    if anki_connect_request('deckNames') is None:
        return

    deck_names = anki_connect_request('deckNames')
    if ANKI_DECK_NAME not in deck_names:
        print(f"Deck '{ANKI_DECK_NAME}' not found. Creating it...")
        anki_connect_request('createDeck', deck=ANKI_DECK_NAME)
        print(f"Deck '{ANKI_DECK_NAME}' created.")

    print(f"\nStep 1: Reading PDF '{pdf_file_path_for_tagging}'...")
    all_extracted_paragraphs = extract_paragraphs_from_pdf(pdf_file_path_for_tagging)
    if not all_extracted_paragraphs:
        print("No paragraphs found in the PDF. Exiting.")
        return

    # Limit the number of paragraphs for testing
    if TEST_LIMIT_NUM_PARAGRAPHS > 0 and TEST_LIMIT_NUM_PARAGRAPHS < len(all_extracted_paragraphs):
        print(f"\nNOTE: For this run, limiting processing to the first {TEST_LIMIT_NUM_PARAGRAPHS} paragraphs.")
        paragraphs_to_process = all_extracted_paragraphs[:TEST_LIMIT_NUM_PARAGRAPHS]
    else:
        paragraphs_to_process = all_extracted_paragraphs

    print(
        f"\nFound {len(all_extracted_paragraphs)} total paragraphs. Will process {len(paragraphs_to_process)} for this run.\n")

    all_cards_data = []
    # Gemini API has a default rate limit (e.g., 60 requests per minute).
    # A 2-second pause is a safe buffer.
    API_PAUSE_SECONDS = 2

    for i, para_text in enumerate(paragraphs_to_process):
        print(f"--- Processing Paragraph {i + 1}/{len(paragraphs_to_process)} ---")
        print(f"  Original Text (first 100 chars): {para_text[:100]}...")

        print("  Step 2: Getting 12-year-old explanation (in Italian)...")
        explained_text = ask_gemini(PROMPT_EXPLAIN_LIKE_12, para_text)
        time.sleep(API_PAUSE_SECONDS)

        if not explained_text:
            print("    Failed to get explanation. Skipping this paragraph.")
            continue
        print(f"    Explained Text (first 100 chars): {explained_text[:100]}...")

        print("  Step 3: Creating multiple cloze deletions (in Italian)...")
        # --- Using the new prompt here ---
        cloze_text = ask_gemini(PROMPT_CREATE_MULTIPLE_CLOZE, explained_text, is_cloze_request=True)
        time.sleep(API_PAUSE_SECONDS)

        if not cloze_text:
            print("    Failed to create cloze text. Skipping this paragraph.")
            continue

        # This check is still valid, it just looks for at least one cloze.
        if not re.search(r"\{\{c\d+::.*?\}\}", cloze_text):
            print(
                f"    Warning: Gemini did not produce a valid cloze format. Output: '{cloze_text}'")
            # The fallback remains simple: cloze the first few words. Better than nothing.
            print("    Attempting to apply a simple fallback cloze...")
            words = explained_text.split()
            if len(words) >= 3:
                cloze_text = f"{{{{c1::{' '.join(words[:3])}}}}} {' '.join(words[3:])}"
                print(f"    Fallback cloze: {cloze_text}")
            else:
                print("    Fallback failed: explanation too short. Skipping.")
                continue
        else:
            print(f"    Cloze Text: {cloze_text}")

        all_cards_data.append((cloze_text, explained_text))

    if all_cards_data:
        print(f"\nStep 4: Adding {len(all_cards_data)} notes to Anki deck '{ANKI_DECK_NAME}'...")
        notes_payload = create_anki_notes_payload(all_cards_data)
        if notes_payload:
            results = anki_connect_request('addNotes', notes=notes_payload)
            if results:
                # Filter out null results which indicate a duplicate or failed card
                num_added = sum(1 for r_id in results if r_id is not None)
                num_failed = len(results) - num_added
                print(f"  Successfully added {num_added} new notes to Anki.")
                if num_failed > 0:
                    print(f"  Skipped {num_failed} notes (likely duplicates or other errors).")
            else:
                print("  Failed to add notes to Anki (AnkiConnect might have reported a general error).")
        else:
            print("  No valid notes were generated to add to Anki.")
    else:
        print("\nNo cards were generated from the PDF.")

    print("\nAutomation complete!")


if __name__ == "__main__":
    main()