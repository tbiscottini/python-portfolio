# ==============================================================================
#                      Esselunga Product Category Updater
# ==============================================================================
#
# DESCRIZIONE:
# Questo script è uno strumento di "arricchimento dati". Il suo scopo è aggiornare
# un file CSV esistente di prodotti Esselunga (generato da un altro scraper)
# che contiene una colonna 'Categoria' con valori mancanti (es. "Nessuna").
#
# COME FUNZIONA:
# 1. Apre un browser controllato da Selenium.
# 2. Visita una lista predefinita di pagine di categorie sul sito Esselunga.
# 3. Per ogni pagina, scorre fino in fondo per caricare tutti i prodotti ("infinite scroll").
# 4. Estrae gli URL di tutti i prodotti visibili e li associa alla categoria corrente.
# 5. Carica il file CSV principale dei prodotti.
# 6. Per ogni prodotto nel CSV con una categoria mancante, controlla se il suo URL
#    corrisponde a uno degli URL raccolti e, in caso affermativo, aggiorna la
#    categoria con quella corretta.
# 7. Salva il file CSV aggiornato, sovrascrivendo quello vecchio.
#
# --- SETUP ---
#
# 1. Installa le librerie richieste:
#    pip install pandas selenium webdriver-manager tqdm
#
# 2. Assicurati che il file CSV da aggiornare si trovi nella stessa cartella dello script
#    e che il suo nome corrisponda a quello definito nella costante NOME_FILE_CSV.
#
# --- ESECUZIONE ---
#
#    python nome_dello_script.py
#
#    Lo script aprirà una finestra di Chrome che non devi chiudere. Al termine,
#    il browser si chiuderà da solo e il file CSV sarà aggiornato.
#
# ==============================================================================

import pandas as pd
import time
import logging
import re
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from tqdm import tqdm
from pathlib import Path

# =========================================================================
# --- CONFIGURAZIONE PRINCIPALE ---
# =========================================================================

# Nome del file CSV da leggere e aggiornare. DEVE essere nella stessa cartella.
NOME_FILE_CSV = 'analisi_nutrizionale_esselunga_FINALE_COMPLETO.csv'

# Numero di tentativi di scroll verso il basso quando la pagina sembra non caricare più nulla.
SCROLL_ATTEMPTS = 3

# Imposta a True per un test rapido solo sulle prime 2 categorie.
# Imposta a False per la run completa su tutte le categorie.
DEBUG_MODE = True

# Lista delle categorie da analizzare. Aggiungi o rimuovi URL secondo necessità.
# Ho mantenuto la tua lista originale perché è una parte fondamentale della logica.
CATEGORIE_URLS = {
    "Frutta Fresca": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002315/frutta-fresca",
    "Verdura Fresca": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002323/verdura-fresca",
    "Agrumi": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002319/agrumi",
    "Insalate E Verdure Lavate": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002327/insalate-e-verdure-lavate",
    "Melanzane E Pomodori": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002426/melanzane-e-pomodori",
    "Pomodori E Pomodorini": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002326/pomodori-e-pomodorini",
    "Insalate E Radicchi": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002325/insalate-e-radicchi",
    "Carote Sedani E Finocchi": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/600000001034786/carote-sedani-e-finocchi",
    "Cavoli Cavolfiori E Broccoli": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/600000001034785/cavoli-cavolfiori-e-broccoli",
    "Verdura Surgelata": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002077/verdura",
    "Minestroni": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001003481/minestroni",
    "Pesce E Carne In Scatola": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002442/pesce-e-carne-in-scatola",
    "Filetti Di Tonno E Salmone": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002445/filetti-di-tonno-e-salmone",
    "Salmone Affumicato": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002032/salmone-affumicato",
    "Bovino E Vitello": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/600000001045605/bovino-e-vitello",
    "Pollo E Tacchino": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/600000001045643/pollo-e-tacchino",
    "Uova": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002382/uova",
    "Legumi E Cereali": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002530/legumi-e-cereali",
    "Legumi In Scatola": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002532/legumi-in-scatola",
    "Vegetariano E Vegano": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001006876/vegetariano-e-vegano",
    "Burger E Cotolette Vegetali": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001021148/burger-e-cotolette-vegetali",
    "Pasta Integrale": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002404/pasta-integrale",
    "Riso": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001021054/riso",
    "Riso Integrale": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/600000001032340/riso-integrale",
    "Cereali": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001011198/cereali",
    "Avena": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001021053/avena",
    "Pane A Fette": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002052/pane-a-fette",
    "Pane E Panini": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002051/pane-e-panini",
    "Gallette": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002055/gallette",
    "Farina Integrale Semi Integrale": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/600000001033661/farina-integrale-semi-integrale",
    "Latte Fresco": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002374/latte-fresco",
    "Yogurt E Dessert": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002346/yogurt-e-dessert",
    "Greco Bianco": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/600000001043621/greco-bianco",
    "Kefir": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/600000001043625/kefir",
    "Latticini E Formaggi Bio": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001021468/latticini-e-formaggi",
    "Bevande Vegetali": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001006879/bevande-vegetali",
    "Olio Extra Vergine Dop Igp": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002512/olio-extra-vergine-dop-igp",
    "Olio Extra Vergine": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002513/olio-extra-vergine",
    "Semi E Condimenti": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002337/semi-e-condimenti",
    "Olive E Lupini": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002336/olive-e-lupini",
    "Spezie E Aromi": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002518/spezie-e-aromi",
    "Aceto Balsamico": "https://spesaonline.esselunga.it/commerce/nav/supermercato/store/menu/300000001002517/aceto-balsamico"
}


# =========================================================================
# --- FUNZIONI DELLO SCRIPT ---
# =========================================================================

def setup_logging():
    """Configura il logging per mostrare messaggi informativi a console."""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def setup_driver() -> webdriver.Chrome:
    """
    Configura e restituisce un'istanza del driver di Selenium Chrome con opzioni
    ottimizzate per lo scraping (es. disabilitando le immagini).
    """
    logging.info("Configurazione del driver Selenium...")
    options = Options()
    # Disabilita il caricamento delle immagini per velocizzare lo scraping
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    # Esegui in modalità "headless" (senza interfaccia grafica) per performance migliori
    # options.add_argument("--headless") # Commentato per permettere il debug visuale
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        return driver
    except Exception as e:
        logging.error(f"Errore durante l'installazione o l'avvio di ChromeDriver: {e}")
        logging.error("Assicurati di avere una connessione internet attiva e che nessun firewall blocchi il download.")
        return None


def scrape_categorie(driver: webdriver.Chrome) -> dict:
    """
    Scorre la lista di URL delle categorie, estrae gli URL dei prodotti e li mappa.

    Args:
        driver: L'istanza del driver di Selenium.

    Returns:
        Un dizionario che mappa gli URL normalizzati dei prodotti ai nomi delle categorie.
    """
    url_a_categoria_map = {}

    categorie_da_processare = list(CATEGORIE_URLS.items())
    if DEBUG_MODE:
        logging.warning(
            "!!! MODALITÀ DEBUG ATTIVA: verranno processate solo le prime 2 categorie per un test rapido. !!!")
        categorie_da_processare = categorie_da_processare[:2]

    for nome_categoria, url_categoria in tqdm(categorie_da_processare, desc="Scraping Categorie"):
        tqdm.write(f"\n--- Inizio scraping per la categoria: {nome_categoria} ---")
        try:
            driver.get(url_categoria)
            initial_pause = random.uniform(4, 7)
            tqdm.write(f"Pagina caricata. Attesa di {initial_pause:.2f} secondi per il caricamento iniziale...")
            time.sleep(initial_pause)

            last_height = driver.execute_script("return document.body.scrollHeight")
            stale_scrolls = 0

            # Ciclo di scroll per caricare tutti i prodotti
            while stale_scrolls < SCROLL_ATTEMPTS:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                scroll_pause = random.uniform(2.5, 4.5)
                time.sleep(scroll_pause)

                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    stale_scrolls += 1
                    tqdm.write(
                        f"Scroll non ha caricato nuovi prodotti (tentativo {stale_scrolls}/{SCROLL_ATTEMPTS})...")
                else:
                    stale_scrolls = 0  # Reset del contatore se vengono caricati nuovi contenuti
                last_height = new_height

            tqdm.write("Scroll terminato. Raccolta e normalizzazione degli URL dei prodotti...")
            product_links = driver.find_elements(By.CSS_SELECTOR, "div.product h3 a.el-link")
            count = 0
            for link in product_links:
                href = link.get_attribute('href')
                if href and "/prodotto/" in href:
                    # Normalizza l'URL per rimuovere parametri superflui e renderlo confrontabile
                    match = re.search(
                        r'(https://spesaonline\.esselunga\.it/commerce/nav/supermercato/store/prodotto/\d+/)', href)
                    if match:
                        normalized_href = match.group(1)
                        if normalized_href not in url_a_categoria_map:
                            url_a_categoria_map[normalized_href] = nome_categoria
                            count += 1
            tqdm.write(f"Trovati {count} nuovi prodotti unici in '{nome_categoria}'.")

            # Pausa educata tra una categoria e l'altra per non sovraccaricare il server
            inter_category_pause = random.uniform(8, 15)
            tqdm.write(f"--- Categoria '{nome_categoria}' completata. Pausa di {inter_category_pause:.2f} secondi. ---")
            time.sleep(inter_category_pause)

        except TimeoutException:
            logging.error(f"Timeout durante il caricamento della pagina per la categoria: {nome_categoria}")
        except Exception as e:
            logging.error(f"Errore imprevisto durante lo scraping della categoria {nome_categoria}: {e}")

    return url_a_categoria_map


def aggiorna_csv(mappa_url: dict, file_path: Path):
    """
    Aggiorna il file CSV principale con le categorie raccolte.

    Args:
        mappa_url: Il dizionario che mappa URL a categoria.
        file_path: Il percorso del file CSV da aggiornare.
    """
    logging.info(f"Caricamento del file CSV: '{file_path}'")
    try:
        # Carica il CSV, mantenendo tutti i dati come stringhe per evitare conversioni indesiderate
        df = pd.read_csv(file_path, sep=';', dtype=str).fillna('')
    except FileNotFoundError:
        logging.error(
            f"ERRORE: File '{file_path}' non trovato. Assicurati che sia nella stessa cartella dello script.")
        return
    except Exception as e:
        logging.error(f"Errore durante la lettura del file CSV: {e}")
        return

    logging.info(f"File caricato. Contiene {len(df)} righe.")

    if 'Categoria' not in df.columns or 'URL' not in df.columns:
        logging.error("ERRORE: Il CSV deve contenere le colonne 'Categoria' e 'URL'.")
        return

    # Selezioniamo solo le righe dove la categoria è mancante o 'Nessuna'
    righe_da_aggiornare_idx = df[df['Categoria'].isin(['', 'Nessuna'])].index

    if righe_da_aggiornare_idx.empty:
        logging.info("Nessun prodotto con categoria mancante. Nessun aggiornamento necessario.")
        return

    logging.info(f"Trovati {len(righe_da_aggiornare_idx)} prodotti con categoria da aggiornare.")

    # Creiamo una Series con le nuove categorie, basata sugli URL delle righe da aggiornare
    mappatura_categorie = df.loc[righe_da_aggiornare_idx, 'URL'].map(mappa_url)

    # Filtriamo per rimuovere i prodotti per cui non abbiamo trovato una categoria
    mappatura_valida = mappatura_categorie.dropna()

    prodotti_aggiornati = len(mappatura_valida)

    if prodotti_aggiornati > 0:
        # Aggiorniamo il DataFrame originale usando gli indici corretti
        df.loc[mappatura_valida.index, 'Categoria'] = mappatura_valida
        logging.info(f"Mappatura completata. Prodotti con categoria aggiornata: {prodotti_aggiornati}")

        logging.info(f"Salvataggio del file CSV aggiornato in '{file_path}'...")
        try:
            df.to_csv(file_path, index=False, sep=';', encoding='utf-8-sig', decimal=',')
            logging.info("Salvataggio completato con successo!")
        except Exception as e:
            logging.error(f"Errore durante il salvataggio del CSV: {e}")
    else:
        logging.info("Nessuna corrispondenza trovata tra gli URL del CSV e quelli appena raccolti.")


def main():
    """Funzione principale che orchestra l'intero processo."""
    setup_logging()

    csv_file_path = Path(NOME_FILE_CSV)
    if not csv_file_path.exists():
        logging.error(f"Il file di input '{NOME_FILE_CSV}' non è stato trovato. Lo script non può continuare.")
        return

    driver = setup_driver()
    if driver is None:
        return  # Termina se il driver non è stato creato

    mappa_url_categorie = {}
    try:
        mappa_url_categorie = scrape_categorie(driver)
    except Exception as e:
        logging.error(f"Si è verificato un errore critico durante la fase di scraping: {e}")
    finally:
        logging.info("Chiusura del browser Selenium.")
        driver.quit()

    if not mappa_url_categorie:
        logging.warning(
            "La mappa delle categorie è vuota. Nessun prodotto è stato raccolto. Il CSV non sarà modificato.")
    else:
        logging.info(f"Scraping completato. Raccolti {len(mappa_url_categorie)} URL unici da mappare.")
        aggiorna_csv(mappa_url_categorie, csv_file_path)

    logging.info("--- OPERAZIONE TERMINATA ---")


if __name__ == "__main__":
    main()