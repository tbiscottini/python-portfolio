# -*- coding: utf-8 -*-
"""
End-to-End Web Scraper for Esselunga Grocery Products.

This script constitutes the data extraction (ETL) part of a larger data pipeline.
It performs the following steps:
1. Fetches all product codes from the Esselunga sitemap.
2. Interactively launches a Selenium browser to allow the user to manually
   authenticate and set a delivery address, then captures the session cookies.
3. Uses multithreading to send concurrent API requests for each product code,
   retrieving detailed product information in JSON format.
4. Parses the complex JSON response, extracting key information like price,
   category, and nutritional values.
5. Implements an advanced normalization system to standardize heterogeneous
   nutritional labels using exact matches, regex, and fuzzy matching.
6. Saves the cleaned and structured data to a CSV file, ready for analysis,
   resuming from where it left off if the output file already exists.

To run this project, you need to install the required dependencies:
pip install pandas requests tqdm beautifulsoup4 selenium webdriver-manager thefuzz python-Levenshtein lxml
"""

import pandas as pd
import re
import requests
from tqdm import tqdm
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random
import os
import logging
import concurrent.futures
import threading
import json
from thefuzz import process

# --- SCRIPT SETTINGS ---
API_BASE_URL = "https://spesaonline.esselunga.it/commerce/resources/displayable/detail/code/"
SITEMAP_URL = "https://spesaonline.esselunga.it/sitemap_product.xml"
OUTPUT_CSV_FILE = 'esselunga_nutritional_data.csv'
LOG_FILE = 'scraper.log'
FAILED_JSON_FILE = 'failed_jsons.json'
CATEGORIES_MAP_FILE = 'mappa_categorie.csv'

# --- SCRAPING & WORKER SETTINGS ---
# Set to False to run on the full dataset, True for a quick test run.
DEBUG_MODE = True
DEBUG_PRODUCT_LIMIT = 100  # Number of products to scrape in debug mode
NUM_WORKERS = 5
REQUEST_TIMEOUT = 15
MAX_RETRIES_ON_429 = 5
BACKOFF_FACTOR = 2

# --- NUTRITIONAL DATA NORMALIZATION SYSTEM ---
# This system standardizes various nutritional labels into a canonical format.
NORMALIZATION_MAP = {
    'energia': 'Energia', 'valore energetico': 'Energia', 'energia kcal': 'Energia',
    'grassi': 'Grassi',
    'acidi grassi saturi': 'Grassi saturi', 'di cui acidi grassi saturi': 'Grassi saturi',
    'di cui saturi': 'Grassi saturi',
    'carboidrati': 'Carboidrati',
    'di cui zuccheri': 'Zuccheri', 'zuccheri': 'Zuccheri',
    'fibre': 'Fibre', 'fibra': 'Fibre',
    'proteine': 'Proteine',
    'sale': 'Sale', 'sodio': 'Sale'
}

REGEX_MAP = {
    'Energia': re.compile(r'energi|kcal|kj'),
    'Grassi saturi': re.compile(r'(di\s+cui\s+)?(acidi\s+grassi\s+)?saturi'),
    'Zuccheri': re.compile(r'(di\s+cui\s+)?zuccheri'),
    'Carboidrati': re.compile(r'carboidrati(?!.*zuccheri)'),
    'Grassi': re.compile(r'grassi(?!.*saturi)'),
    'Fibre': re.compile(r'fibr[ae]'),
    'Proteine': re.compile(r'proteine'),
    'Sale': re.compile(r'sale|sodio'),
}

REGEX_PRIORITY_ORDER = [
    'Grassi saturi', 'Zuccheri', 'Grassi', 'Carboidrati',
    'Energia', 'Proteine', 'Fibre', 'Sale'
]

CANONICAL_LABELS = list(REGEX_PRIORITY_ORDER)

# List of terms to ignore to reduce noise and false positives during normalization.
IGNORE_LIST = [
    'vitamina', 'vit', 'calcio', 'ferro', 'zinco', 'iodio', 'rame', 'manganese',
    'cromo', 'selenio', 'molibdeno', 'magnesio', 'potassio', 'fosforo', 'niacina',
    'biotina', 'riboflavina', 'tiamina', 'folico', 'pantotenico', 'colina', 'fluoruro',
    'vnr', 'nrv', 'riferimento', 'porzion', 'grezza', 'umidit', 'ceneri',
    'additivi', 'componenti', 'taurina', 'valori nutritivi', 'polioli',
    'solfato', 'cloruro', 'omega', 'carnitina', 'metionina', 'lisina', 'istidina',
    'residuo fisso', 'conducibilit', 'durezza', 'bicarbonato', 'anidride carbonica',
    'sorgente', 'silice', 'nitrato', 'ph', 'e.s', 'e.m', 'o.e', 'lactobacillus',
    'bifidobacterium', 'melatonina', 'triptofano', 'griffonia', 'passiflora',
    'valeriana', 'biancospino', 'tiglio', 'melissa'
]


def clean_text(text: str) -> str:
    """Lowercase, strip, and remove non-alphanumeric characters from a string."""
    if not isinstance(text, str): return ""
    cleaned = text.lower().strip()
    cleaned = re.sub(r'[^a-z0-9\s]', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned


CLEAN_NORMALIZATION_MAP = {clean_text(k): v for k, v in NORMALIZATION_MAP.items()}


def normalize_nutrient(label: str, fuzzy_threshold: int = 85) -> str | None:
    """
    Normalizes a nutritional label to a canonical name using a multi-step approach:
    1. Exact match on a cleaned dictionary.
    2. Regex matching for common patterns.
    3. Fuzzy string matching as a fallback.
    """
    if not label or not label.strip(): return None
    cleaned_label = clean_text(label)
    if not cleaned_label: return None
    if any(word in cleaned_label for word in IGNORE_LIST):
        return None
    if cleaned_label in CLEAN_NORMALIZATION_MAP:
        return CLEAN_NORMALIZATION_MAP[cleaned_label]
    for standard_name in REGEX_PRIORITY_ORDER:
        if REGEX_MAP[standard_name].search(cleaned_label):
            return standard_name
    best_match = process.extractOne(cleaned_label, CANONICAL_LABELS)
    if best_match and best_match[1] >= fuzzy_threshold:
        return best_match[0]
    logging.info(f"Potentially useful but unrecognized label: '{label}' (cleaned: '{cleaned_label}')")
    return None


# ==============================================================================
# --- UTILITY AND SETUP FUNCTIONS ---
# ==============================================================================

def get_all_product_codes_from_sitemap(sitemap_url: str) -> list:
    """Downloads and parses a sitemap to extract all product codes."""
    logging.info(f"Downloading sitemap from: {sitemap_url}")
    try:
        response = requests.get(sitemap_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml-xml')
        product_codes = [m.group(1) for loc in soup.find_all('loc') if (m := re.search(r'/prodotto/(\d+)/', loc.text))]
        logging.info(f"Sitemap parsed. Found {len(product_codes)} product codes.")
        return product_codes
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to download sitemap. {e}")
        return []


def get_session_cookies_with_selenium() -> list | None:
    """Launches a Selenium browser for manual authentication to capture session cookies."""
    driver = None
    logging.info("Launching interactive Selenium browser for manual authentication...")
    try:
        options = Options()
        options.add_argument("--start-maximized")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get("https://spesaonline.esselunga.it")
        print("\n" + "="*80 +
              "\n>>> ACTION REQUIRED <<<\n"
              "A browser window has opened. Please log in or set a delivery address.\n"
              "The script will wait up to 5 minutes for the session to be configured.\n"
              "Once done, the window will close automatically and scraping will begin.\n" +
              "="*80 + "\n")
        wait = WebDriverWait(driver, 300)
        logging.info("Waiting for user to set address/login (waiting for 'GUEST_ADDRESS' cookie)...")
        wait.until(lambda d: d.get_cookie('GUEST_ADDRESS'))
        logging.info("Session cookie found! Capturing all cookies.")
        cookies = driver.get_cookies()
        if not cookies:
            logging.error("No cookies captured after manual operation.")
            return None
        return cookies
    except Exception as e:
        if "TimeoutException" in str(e):
            logging.critical("Timeout expired. Manual operation was not completed in time.")
        else:
            logging.critical(f"A critical error occurred during Selenium setup: {e}")
        return None
    finally:
        if driver:
            driver.quit()
            logging.info("Selenium browser closed.")


def load_categories_map(file_mappa: str) -> dict:
    """Loads the category ID to category path mapping from a CSV file."""
    if not os.path.exists(file_mappa):
        logging.warning(f"Category map file '{file_mappa}' not found. Products will not be categorized.")
        return {}
    try:
        df_mappa = pd.read_csv(file_mappa, sep=';', encoding='utf-8-sig')
        mappa = pd.Series(df_mappa.percorso_completo.values, index=df_mappa.id_categoria.astype(str)).to_dict()
        logging.info(f"Category map loaded successfully from '{file_mappa}' with {len(mappa)} entries.")
        return mappa
    except Exception as e:
        logging.error(f"Error loading category map: {e}")
        return {}


def parse_product_json(full_data: dict, product_code: str, mappa_categorie: dict) -> dict | None:
    """Parses the full JSON response for a single product to extract relevant data."""
    def robust_float_conversion(s: str) -> float | None:
        if not isinstance(s, str): return None
        try:
            s = s.strip()
            if ',' in s: s = s.replace('.', '').replace(',', '.')
            return float(s)
        except (ValueError, TypeError):
            return None

    def extract_value_in_grams(text: str) -> str | None:
        if not isinstance(text, str): return None
        match = re.search(r'([\d.,]+)\s*g', text, re.IGNORECASE)
        return match.group(1) if match else None

    try:
        if not full_data or 'error' in full_data: return None
        product_data = full_data.get('displayableProduct')
        if not product_data:
            logging.warning(f"Product {product_code}: 'displayableProduct' key missing from JSON.")
            return None

        prodotto = {'ID': product_data.get('code'), 'Nome Prodotto': product_data.get('description'),
                    'URL': f"https://spesaonline.esselunga.it/commerce/nav/supermercato/store/prodotto/{product_data.get('code')}/"}

        prodotto['Categoria'] = "N/A"
        menu_path_ids = product_data.get('menuItemPath')
        if menu_path_ids and isinstance(menu_path_ids, list) and len(menu_path_ids) > 0:
            id_categoria_specifica = str(menu_path_ids[-1])
            prodotto['Categoria'] = mappa_categorie.get(id_categoria_specifica, f"Unknown_ID_{id_categoria_specifica}")

        prodotto['Prezzo al Kg'] = None
        if label := product_data.get('label'):
            if '€' in label:
                if match_kg_l := re.search(r'(\d+[.,]\d+)\s*€\s*/\s*(kg|l)', label):
                    if (prezzo := robust_float_conversion(match_kg_l.group(1))) is not None:
                        prodotto['Prezzo al Kg'] = prezzo
                elif match_g := re.search(r'(\d+[.,]\d+)\s*€\s*/\s*g', label):
                    if (prezzo := robust_float_conversion(match_g.group(1))) is not None:
                        prodotto['Prezzo al Kg'] = prezzo * 1000

        for key in CANONICAL_LABELS:
            prodotto[key] = None

        informations_data = full_data.get('informations', [])
        dati_nutrizionali_trovati = False

        spm_data = next((info for info in informations_data if info.get('type') == 'SPM_VALORI_NUTRIZIONALI'), None)
        if spm_data and 'cells' in spm_data:
            for label, value_list in spm_data['cells'].items():
                if not value_list: continue
                nome_normalizzato = normalize_nutrient(label)
                if not nome_normalizzato: continue
                raw_value_text = value_list[0]
                valore_da_usare = None
                if nome_normalizzato == 'Energia':
                    if match_kcal := re.search(r'([\d.,]+)\s*kcal', raw_value_text, re.IGNORECASE):
                        valore_da_usare = match_kcal.group(1)
                else:
                    valore_da_usare = extract_value_in_grams(raw_value_text)
                if valore_da_usare and (valore_numerico := robust_float_conversion(valore_da_usare)) is not None and prodotto.get(nome_normalizzato) is None:
                    prodotto[nome_normalizzato] = valore_numerico
                    dati_nutrizionali_trovati = True

        if not dati_nutrizionali_trovati:
            if html_nutrizionale := next((info.get('value') for info in informations_data if info.get('label') == 'Valori nutrizionali'), None):
                soup_tabella = BeautifulSoup(html_nutrizionale, 'html.parser')
                last_main_label = None
                for riga in soup_tabella.find_all('tr'):
                    celle = riga.find_all('td')
                    if len(celle) < 2: continue
                    testo_cella_label = celle[0].get_text(separator=' ', strip=True)
                    testo_cella_valore = celle[1].text.strip()
                    if not any(char.isdigit() for char in testo_cella_valore): continue
                    nome_normalizzato = normalize_nutrient(testo_cella_label)
                    if nome_normalizzato:
                        last_main_label = nome_normalizzato
                        valore_da_usare = None
                        if nome_normalizzato == 'Energia':
                            if match_kcal := re.search(r'([\d.,]+)\s*kcal', testo_cella_valore, re.IGNORECASE):
                                valore_da_usare = match_kcal.group(1)
                        else:
                            valore_da_usare = extract_value_in_grams(testo_cella_valore)
                        if valore_da_usare and (valore_numerico := robust_float_conversion(valore_da_usare)) is not None and prodotto.get(nome_normalizzato) is None:
                            prodotto[nome_normalizzato] = valore_numerico
                            dati_nutrizionali_trovati = True
                    elif not testo_cella_label.strip() and last_main_label == 'Energia':
                        if match_kcal := re.search(r'([\d.,]+)\s*kcal', testo_cella_valore, re.IGNORECASE):
                            if (valore_numerico := robust_float_conversion(match_kcal.group(1))) is not None:
                                prodotto['Energia'] = valore_numerico
                                dati_nutrizionali_trovati = True
        return prodotto if dati_nutrizionali_trovati else None
    except Exception as e:
        logging.error(f"Critical parsing error on product JSON {product_code}: {e}")
        return None


def process_product_code(product_code: str, session: requests.Session, session_cookies: list, stop_event: threading.Event, mappa_categorie: dict) -> tuple | str | None:
    """
    The main worker function that processes a single product code by fetching and parsing its data.
    Implements retry logic with exponential backoff for rate limiting errors.
    """
    if stop_event.is_set(): return None
    api_url = f"{API_BASE_URL}{product_code}"
    cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in session_cookies])
    headers = {'Accept': 'application/json, text/plain, */*', 'Cookie': cookie_string,
               'Referer': f'https://spesaonline.esselunga.it/commerce/nav/supermercato/store/prodotto/{product_code}/',
               'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
               'X-PAGE-PATH': 'supermercato'}
    for attempt in range(MAX_RETRIES_ON_429):
        if stop_event.is_set(): return None
        try:
            response = session.get(api_url, headers=headers, timeout=REQUEST_TIMEOUT)
            if response.status_code == 404:
                logging.info(f"Product {product_code} not found (404). Skipping.")
                return None
            response.raise_for_status()
            full_data = response.json()
            if parsed_product := parse_product_json(full_data, product_code, mappa_categorie):
                return 'SUCCESS', parsed_product
            else:
                logging.debug(f"Product {product_code}: Parsing failed. Saving JSON for analysis.")
                return 'PARSE_FAILURE', full_data
        except requests.exceptions.Timeout:
            logging.critical(f"TIMEOUT on product {product_code}. INITIATING GLOBAL SHUTDOWN.")
            stop_event.set()
            return "TIMEOUT_STOP"
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                if attempt < MAX_RETRIES_ON_429 - 1:
                    wait_time = BACKOFF_FACTOR * (2 ** attempt) + random.uniform(0, 1)
                    logging.warning(f"Product {product_code}: Rate limit (429). Retrying in {wait_time:.2f}s...")
                    time.sleep(wait_time)
                else:
                    logging.error(f"Product {product_code}: Exceeded {MAX_RETRIES_ON_429} retries for 429 error. Skipping.")
                    return None
            else:
                logging.warning(f"Unhandled HTTP error on product {product_code}: {e}. Skipping.")
                return None
        except requests.exceptions.RequestException as e:
            logging.warning(f"Network error on product {product_code}: {e}. Skipping.")
            return None
    return None


def main():
    """Main execution block to orchestrate the entire scraping process."""
    log_level = logging.DEBUG if DEBUG_MODE else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8'),
                                  logging.StreamHandler()])
    logging.info(f"--- Starting Esselunga Scraper ---")

    mappa_categorie = load_categories_map(CATEGORIES_MAP_FILE)
    codici_totali = get_all_product_codes_from_sitemap(SITEMAP_URL)
    if not codici_totali:
        return

    codici_gia_analizzati = set()
    file_esistente = os.path.exists(OUTPUT_CSV_FILE)
    if file_esistente and os.path.getsize(OUTPUT_CSV_FILE) > 0:
        try:
            df_esistente = pd.read_csv(OUTPUT_CSV_FILE, sep=';', usecols=['ID'], on_bad_lines='skip')
            codici_gia_analizzati = set(df_esistente['ID'].astype(str))
            logging.info(f"Found {len(codici_gia_analizzati)} existing products in CSV. They will be skipped.")
        except Exception as e:
            logging.warning(f"Could not read existing CSV file: {e}. Starting from scratch.")
            file_esistente = False

    codici_da_analizzare = [code for code in codici_totali if code not in codici_gia_analizzati]

    if DEBUG_MODE:
        logging.warning(f"!!! DEBUG MODE is ACTIVE: Analyzing a maximum of {DEBUG_PRODUCT_LIMIT} random new products. !!!")
        if len(codici_da_analizzare) > DEBUG_PRODUCT_LIMIT:
            codici_da_analizzare = random.sample(codici_da_analizzare, DEBUG_PRODUCT_LIMIT)
            logging.info(f"Sampled {len(codici_da_analizzare)} products for this debug run.")

    if not codici_da_analizzare:
        logging.info("No new products to analyze. Job finished.")
        return

    logging.info(f"Total new products to analyze: {len(codici_da_analizzare)}")
    cookies = get_session_cookies_with_selenium()
    if not cookies:
        logging.critical("Could not retrieve session cookies. Exiting.")
        return

    stop_event = threading.Event()
    lista_nuovi_prodotti = []
    lista_json_problematici = []

    with requests.Session() as session:
        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
            logging.info(f"Starting {NUM_WORKERS} workers to analyze {len(codici_da_analizzare)} products...")
            future_to_code = {executor.submit(process_product_code, code, session, cookies, stop_event, mappa_categorie): code for code in codici_da_analizzare}

            for future in tqdm(concurrent.futures.as_completed(future_to_code), total=len(codici_da_analizzare), desc="Analyzing Products"):
                if stop_event.is_set(): break
                try:
                    risultato = future.result()
                    if risultato:
                        status, data = risultato
                        if status == 'SUCCESS':
                            lista_nuovi_prodotti.append(data)
                        elif status == 'PARSE_FAILURE':
                            lista_json_problematici.append(data)
                except Exception as exc:
                    code = future_to_code[future]
                    logging.error(f'Product {code} generated an unexpected exception: {exc}')

            if stop_event.is_set():
                logging.warning("Stop signal received. Cancelling remaining tasks...")
                for f in future_to_code: f.cancel()
                executor.shutdown(wait=True, cancel_futures=True)

    logging.info(f"Process finished. Valid products: {len(lista_nuovi_prodotti)}. Failed JSONs: {len(lista_json_problematici)}.")

    if lista_nuovi_prodotti:
        scrivi_header = not file_esistente or os.path.getsize(OUTPUT_CSV_FILE) == 0
        df_nuovi = pd.DataFrame(lista_nuovi_prodotti)
        colonne_ordinate = ['ID', 'Nome Prodotto', 'Prezzo al Kg', 'Categoria', 'URL'] + CANONICAL_LABELS
        df_nuovi = df_nuovi.reindex(columns=colonne_ordinate)
        df_nuovi.to_csv(OUTPUT_CSV_FILE, mode='a', index=False, header=scrivi_header, encoding='utf-8-sig', sep=';', decimal=',')
        logging.info(f"Saved {len(lista_nuovi_prodotti)} new products to '{OUTPUT_CSV_FILE}'")
    else:
        logging.info("No new valid products were collected.")

    if lista_json_problematici:
        with open(FAILED_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(lista_json_problematici, f, indent=2, ensure_ascii=False)
        logging.info(f"Saved {len(lista_json_problematici)} failed JSONs to '{FAILED_JSON_FILE}'.")

    if stop_event.is_set():
        logging.critical("--- SCRIPT INTERRUPTED DUE TO TIMEOUT. COLLECTED DATA HAS BEEN SAVED. ---")
    else:
        logging.info("--- ALL PRODUCTS PROCESSED. JOB FINISHED! ---")

# ==============================================================================
# --- MAIN EXECUTION BLOCK ---
# ==============================================================================
if __name__ == "__main__":
    main()