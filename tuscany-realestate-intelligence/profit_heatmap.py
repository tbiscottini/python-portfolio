import os
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv

# =====================================================================
# CONFIGURATION & PATHS
# =====================================================================
# Calcola la root del progetto (esce dalla cartella 'visualizations')
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if '__file__' in locals() else os.getcwd()
load_dotenv(os.path.join(BASE_DIR, ".env"))

PREMIUM_DB = os.path.join(BASE_DIR, "data_master", "market_master_database.csv")
FLIPPING_DB = os.path.join(BASE_DIR, "data_master", "market_flipping_database.csv")
OUTPUT_HTML = os.path.join(BASE_DIR, "visualizations", "treasure_map_toscana.html")

RENO_COST_MQ = int(os.getenv("RENO_COST_MQ", 1000))

# Coordinate centrali per le province toscane
COORDINATE_PROVINCE = {
    "FI": {"lat": 43.7696, "lon": 11.2558, "nome": "Firenze"},
    "LU": {"lat": 43.8429, "lon": 10.5027, "nome": "Lucca"},
    "AR": {"lat": 43.4631, "lon": 11.8778, "nome": "Arezzo"},
    "SI": {"lat": 43.3188, "lon": 11.3308, "nome": "Siena"},
    "PI": {"lat": 43.7085, "lon": 10.4036, "nome": "Pisa"},
    "LI": {"lat": 43.5485, "lon": 10.3106, "nome": "Livorno"},
    "PT": {"lat": 43.9330, "lon": 10.9121, "nome": "Pistoia"},
    "PO": {"lat": 43.8777, "lon": 11.1022, "nome": "Prato"},
    "GR": {"lat": 42.7605, "lon": 11.1101, "nome": "Grosseto"},
    "MS": {"lat": 44.0367, "lon": 10.1417, "nome": "Massa-Carrara"}
}


def create_profit_heatmap():
    print("🗺️ Generazione Mappa del Tesoro in corso...")

    if not os.path.exists(PREMIUM_DB) or not os.path.exists(FLIPPING_DB):
        print(f"🛑 Errore: Database mancanti in {os.path.join(BASE_DIR, 'data_master')}")
        return

    # 1. Caricamento Dati
    df_p = pd.read_csv(PREMIUM_DB)
    df_f = pd.read_csv(FLIPPING_DB)

    # 2. Pulizia GeoID e calcolo Mediane Premium
    df_p_clean = df_p[df_p['GeoID'].notna() & (~df_p['GeoID'].str.startswith('ERROR', na=True))]
    premium_medians = df_p_clean.groupby('GeoID')['Price_MQ'].median().reset_index()
    premium_medians.columns = ['GeoID', 'Premium_Median_MQ']

    # 3. Join e Calcolo del Profitto Potenziale
    df = pd.merge(df_f, premium_medians, on='GeoID', how='inner')
    df['Potential_Profit'] = (df['Premium_Median_MQ'] * df['Area']) - (df['Price'] + (df['Area'] * RENO_COST_MQ))

    # Filtro sanità: togliamo profitti negativi e follie statistiche
    df = df[(df['Potential_Profit'] > 0) & (df['Premium_Median_MQ'] <= 12000)]

    if df.empty:
        print("Nessun profitto positivo da mappare. Controlla i database.")
        return

    # 4. Estrazione Provincia e Coordinate dal GeoID
    def get_coords(geoid):
        # Esempio GeoID: 0-EU-IT-FI-01-001... -> prende 'FI'
        parts = str(geoid).split('-')
        prov = parts[3] if len(parts) > 3 else "Unknown"
        return prov, COORDINATE_PROVINCE.get(prov, {}).get('lat'), COORDINATE_PROVINCE.get(prov, {}).get('lon')

    df[['Provincia', 'lat', 'lon']] = df['GeoID'].apply(lambda x: pd.Series(get_coords(x)))
    df = df.dropna(subset=['lat', 'lon'])

    # 5. Creazione Mappa di Calore
    fig = px.density_mapbox(
        df,
        lat='lat',
        lon='lon',
        z='Potential_Profit',
        radius=35,
        center=dict(lat=43.7, lon=11.0),
        zoom=7,
        mapbox_style="carto-darkmatter",
        title="MAPPA DEL TESORO: Concentrazione Profitto Potenziale (€) in Toscana",
        hover_data={"Title": True, "Potential_Profit": ":.0f", "Provincia": True},
        color_continuous_scale="Reds"
    )

    # Miglioramento estetica per il Portfolio
    fig.update_layout(
        font=dict(family="Courier New, monospace", size=14, color="white"),
        title_font=dict(size=22),
        margin={"r": 0, "t": 50, "l": 0, "b": 0}
    )

    # 6. Salvataggio
    fig.write_html(OUTPUT_HTML)
    print(f"🔥 Fatto! Mappa salvata in: {OUTPUT_HTML}")
    print("👉 Apri il file nel browser, fai uno screenshot, e salvalo come 'profit_heatmap.png' per GitHub!")


if __name__ == "__main__":
    create_profit_heatmap()