import requests
import pandas as pd
from pathlib import Path

# URL dell'API che restituisce la struttura del menù/categorie
URL_CATEGORIE = "https://spesaonline.esselunga.it/commerce/resources/nav/supermercato"

# Nome del file di output
OUTPUT_FILE = Path("mappa_categorie.csv")


def scarica_e_processa_categorie():
    """
    Scarica il JSON con la struttura delle categorie, lo elabora per creare
    un percorso gerarchico e lo salva in un file CSV.
    """
    print(f"📥 Sto scaricando l'albero delle categorie da {URL_CATEGORIE}...")
    try:
        response = requests.get(URL_CATEGORIE, timeout=10)
        response.raise_for_status()  # Solleva un errore se la richiesta fallisce (es. 404, 500)
        data = response.json()
        print("✅ Albero delle categorie scaricato con successo.")
    except requests.exceptions.RequestException as e:
        print(f"❌ Errore durante il download delle categorie: {e}")
        return

    # Estraiamo tutte le voci del menù in una lista
    menu_items = data.get('leftMenuItems', [])
    if not menu_items:
        print("❌ Non sono state trovate voci di menù ('leftMenuItems') nel JSON.")
        return

    # Creiamo un dizionario per un accesso rapido: id -> {label, parentId}
    items_map = {item['id']: {'label': item['label'], 'parentId': item['parentMenuItemId']} for item in menu_items}

    categorie_finali = []

    print("\n🏗️  Sto costruendo i percorsi gerarchici per ogni categoria...")
    for item_id, item_details in items_map.items():
        path_list = []
        current_id = item_id

        # Ricostruisce il percorso risalendo l'albero tramite parentId
        while current_id is not None:
            node = items_map.get(current_id)
            if node:
                path_list.append(node['label'])
                current_id = node.get('parentId')
            else:
                # Se non troviamo un genitore, interrompiamo il ciclo
                break

        # Invertiamo la lista per avere il percorso corretto (da radice a foglia)
        path_list.reverse()

        # Creiamo una stringa del percorso, es. "Freschi -> Latticini -> Uova"
        path_str = " -> ".join(path_list)

        categorie_finali.append({
            'id_categoria': item_id,
            'percorso_completo': path_str,
            'categoria_livello_1': path_list[0] if len(path_list) > 0 else None,
            'categoria_livello_2': path_list[1] if len(path_list) > 1 else None,
            'categoria_livello_3': path_list[2] if len(path_list) > 2 else None,
        })

    # Creiamo un DataFrame pandas e lo salviamo in CSV
    df_categorie = pd.DataFrame(categorie_finali)

    # Pulizia: spesso la radice è una categoria generica come "SUPERMERCATO"
    # La escludiamo per rendere i percorsi più puliti.
    if 'categoria_livello_1' in df_categorie.columns and df_categorie['categoria_livello_1'].nunique() == 1:
        print("ℹ️  Rimuovo il livello radice comune per pulire i percorsi.")
        df_categorie['percorso_completo'] = df_categorie['percorso_completo'].str.split(' -> ').str[1:].str.join(' -> ')

    try:
        df_categorie.to_csv(OUTPUT_FILE, index=False, sep=';')
        print(f"\n✅ Mappa delle categorie salvata con successo in '{OUTPUT_FILE}'.")
        print(f"   Trovate e processate {len(df_categorie)} categorie.")
    except Exception as e:
        print(f"❌ Errore durante il salvataggio del file CSV: {e}")


if __name__ == "__main__":
    # CORRETTO
    scarica_e_processa_categorie()