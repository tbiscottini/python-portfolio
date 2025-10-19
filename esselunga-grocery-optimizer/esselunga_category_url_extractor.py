import requests
import pandas as pd
import re
from pathlib import Path
from xml.etree import ElementTree
from typing import List, Dict, Optional

# --- CONFIGURAZIONE ---
URL_SITEMAP = "https://spesaonline.esselunga.it/sitemap_listing_page.xml"
OUTPUT_FILE = Path("lista_url_categorie.csv")


# --- FINE CONFIGURAZIONE ---


def fetch_sitemap_content(url: str) -> Optional[bytes]:
    """
    Scarica il contenuto di un sitemap XML da un URL.

    Args:
        url: L'URL del sitemap da scaricare.

    Returns:
        Il contenuto XML come bytes in caso di successo, altrimenti None.
    """
    print(f"📥 Sto scaricando il sitemap da {url}...")
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()  # Solleva un errore per status code 4xx/5xx
        print("✅ Sitemap scaricato con successo.")
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"❌ Errore durante il download del sitemap: {e}")
        return None


def parse_sitemap_data(xml_content: bytes) -> List[Dict]:
    """
    Analizza il contenuto XML di un sitemap ed estrae gli URL e gli ID delle categorie.

    Args:
        xml_content: Il contenuto XML grezzo del sitemap.

    Returns:
        Una lista di dizionari, ognuno contenente 'id_categoria' e 'url_pagina_categoria'.
    """
    url_list = []
    namespaces = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

    print("🔍 Sto analizzando il contenuto XML e estraendo gli URL...")
    try:
        root = ElementTree.fromstring(xml_content)

        for url_node in root.findall('s:url', namespaces):
            loc_node = url_node.find('s:loc', namespaces)
            if loc_node is not None and loc_node.text:
                url = loc_node.text
                # Usiamo un'espressione regolare per estrarre l'ID in modo robusto
                match = re.search(r'/menu/(\d+)/', url)
                if match:
                    id_categoria = int(match.group(1))
                    url_list.append({
                        'id_categoria': id_categoria,
                        'url_pagina_categoria': url
                    })
    except ElementTree.ParseError as e:
        print(f"❌ Errore durante l'analisi del file XML: {e}")
        return []

    if not url_list:
        print("⚠️ Nessun URL di categoria valido trovato nel sitemap.")
    else:
        print(f"✅ Estrazione completata. Trovati {len(url_list)} URL di categorie.")

    return url_list


def save_data_to_csv(data: List[Dict], output_path: Path) -> None:
    """
    Salva una lista di dati in un file CSV utilizzando Pandas.

    Args:
        data: La lista di dizionari da salvare.
        output_path: Il percorso del file CSV di output.
    """
    if not data:
        print("ℹ️ Nessun dato da salvare. Il file CSV non verrà creato.")
        return

    print(f"💾 Sto salvando i dati nel file '{output_path}'...")
    try:
        df_urls = pd.DataFrame(data)
        df_urls.to_csv(output_path, index=False, sep=';')
        print(f"✅ File CSV salvato con successo.")
    except Exception as e:
        print(f"❌ Errore durante il salvataggio del file CSV: {e}")


def main():
    """
    Funzione principale che orchestra il processo di scraping.
    """
    print("--- Avvio Script Estrattore URL Categorie Esselunga ---")

    # 1. Scarica il contenuto
    sitemap_content = fetch_sitemap_content(URL_SITEMAP)
    if not sitemap_content:
        print("--- Script terminato a causa di un errore nel download. ---")
        return

    # 2. Analizza i dati
    parsed_data = parse_sitemap_data(sitemap_content)
    if not parsed_data:
        print("--- Script terminato perché non sono stati trovati dati validi. ---")
        return

    # 3. Salva i dati
    save_data_to_csv(parsed_data, OUTPUT_FILE)

    print("--- Script completato con successo. ---")


if __name__ == "__main__":
    main()