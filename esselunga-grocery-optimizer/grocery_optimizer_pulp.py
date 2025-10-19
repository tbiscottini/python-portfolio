# =========================================================================
# === Grocery Basket Optimizer using Linear Programming (v1.2 - Robust) ===
#
# AUTHOR: Tommaso Biscottini
# GITHUB: https://github.com/tbiscottini/python-portfolio
#
# DESCRIPTION:
# This script uses Linear Programming to find the lowest-cost daily grocery
# basket that satisfies complex nutritional and dietary constraints.
#
# VERSION 1.2 - FIX: Implemented a robust "Big-M" formulation to correctly
# enforce the minimum variety constraint, which was previously ignored by the
# solver in some configurations.
# =========================================================================

import pandas as pd
import pulp
import logging
import io


# =========================================================================
# === 1. LOGGING CONFIGURATION ===
def setup_logging():
    logger = logging.getLogger('DietOptimizer')
    logger.setLevel(logging.INFO)
    if logger.hasHandlers():
        logger.handlers.clear()
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(levelname)s] %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger


logger = setup_logging()

# =========================================================================
# === 2. EMBEDDED SAMPLE DATASET ===
dati_embedded = """Nome Prodotto;Prezzo al Kg;Categoria;Energia;Grassi;Carboidrati;Proteine;Fibre;Zuccheri;Sale
Petto di Pollo a Fette;10.99;Pollo E Tacchino;110;1.5;0;24;0;0;0.1
Salmone Fresco Filetto;25.99;Pesce Fresco;208;13;0;22;0;0;0.1
Uova Fresche Biologiche;6.80;Uova;143;9.5;0.7;13;0;0.7;0.4
Olio Extra Vergine di Oliva;8.50;Olio Extra Vergine;824;91.6;0;0;0;0;0
Riso Integrale;3.50;Riso Integrale;362;2.9;72;7.9;3.5;0.9;0
Lenticchie Secche;3.90;Legumi E Cereali;352;1;53;25;14;1.8;0
Yogurt Greco 0% Grassi;7.50;Yogurt E Dessert;57;0;3.9;10;0;3.9;0.1
Spinaci Freschi;5.90;Verdura Fresca;23;0.4;3.6;2.9;2.2;0.4;0.8
Broccoli Freschi;3.50;Verdura Fresca;34;0.4;6.6;2.8;2.6;1.7;0.3
Mele Golden;2.50;Frutta Fresca;52;0.2;14;0.3;2.4;10;0
Banane;1.90;Frutta Fresca;89;0.3;23;1.1;2.6;12;0
Tonno al Naturale;14.50;Pesce E Carne In Scatola;116;0.8;0;26;0;0;1.1
Fesa di Tacchino Affettata;19.90;Pollo E Tacchino;105;1.2;0;24;0;0;1.8
Fiocchi di Avena;2.80;Cereali;379;6.9;60;14;10;1.2;0
Merluzzo Filetti;18.90;Pesce Fresco;82;0.7;0;19;0;0;0.2
Ceci in Scatola;2.50;Legumi E Cereali;139;2.4;21;7;7.7;0.7;0.4
Pomodori a Grappolo;3.20;Verdura Fresca;18;0.2;3.9;0.9;1.2;2.6;0.1
Bresaola della Valtellina;39.90;Carne Bovina;151;2.6;0;32;0;0;4
Mandorle Sgusciate;15.00;Semi E Condimenti;579;49;21;21;12;4.4;0.01
"""

# =========================================================================
# === 3. PROBLEM CONFIGURATION (OBJECTIVES & CONSTRAINTS) ===
TARGETS = {
    'Energia': {'min': 1900, 'max': 2000},
    'Proteine': {'min': 150, 'max': None},
    'Grassi': {'min': 50, 'max': 60},
    'Carboidrati': {'min': 200, 'max': 230},
    'Fibre': {'min': 30, 'max': None},
    'Zuccheri': {'min': 0, 'max': 50},
    'Sale': {'min': 0, 'max': 5}
}

MAX_KG_PER_PRODOTTO_CRUDO = 0.5
MAX_KG_PER_CONDIMENTO = 0.05
MIN_PRODOTTI_DIVERSI = 5
MAX_PRODOTTI_DIVERSI = 12

VINCOLI_CATEGORIA = {
    'quantita_minima_kg': {
        'Verdura Fresca': 0.2,
        'Frutta Fresca': 0.15,
        'Olio Extra Vergine': 0.02
    },
    'quantita_minima_kg_gruppo': {
        'Fonte Proteica Primaria': {
            'categorie': ['Pollo E Tacchino', 'Pesce Fresco', 'Uova', 'Carne Bovina', 'Pesce E Carne In Scatola'],
            'min_kg': 0.2
        }
    }
}


# =========================================================================
# === 4. CORE FUNCTIONS ===

def prepara_dati() -> pd.DataFrame:
    logger.info("--- Phase 1: Loading and Preparing Data ---")
    try:
        df = pd.read_csv(io.StringIO(dati_embedded), sep=';')
        logger.info(f"Sample data loaded successfully. Found {len(df)} products.")
    except Exception as e:
        logger.error(f"Critical error while parsing embedded data: {e}")
        return None

    colonne_nutrizionali = ['Energia', 'Grassi', 'Carboidrati', 'Proteine', 'Fibre', 'Zuccheri', 'Sale']
    colonne_essenziali = ['Nome Prodotto', 'Prezzo al Kg', 'Categoria'] + colonne_nutrizionali

    df = df[colonne_essenziali].copy()
    df.dropna(subset=colonne_essenziali, inplace=True)
    df = df[df['Prezzo al Kg'] > 0]
    for col in colonne_nutrizionali:
        df[col] = df[col] * 10
    logger.info("Nutritional values converted to units per Kg.")
    df.reset_index(drop=True, inplace=True)
    logger.info(f"Preparation complete. Candidate pool of {len(df)} products is ready.")
    return df


def ottimizza_dieta(pool_df: pd.DataFrame):
    logger.info("--- Phase 2: Defining and Solving the Optimization Model ---")
    model = pulp.LpProblem("Optimal_Balanced_Diet", pulp.LpMinimize)

    # ### <<< INIZIO MODIFICHE FONDAMENTALI >>> ###
    # Variabili continue per la quantità di ogni prodotto
    quantita = pulp.LpVariable.dicts("quantita", pool_df.index, lowBound=0, cat='Continuous')
    # Variabili binarie per indicare SE un prodotto è usato (1) o no (0)
    prodotto_usato = pulp.LpVariable.dicts("prodotto_usato", pool_df.index, cat='Binary')

    # Obiettivo: minimizzare il costo totale
    model += pulp.lpSum([pool_df.loc[i, 'Prezzo al Kg'] * quantita[i] for i in pool_df.index]), "Costo_Totale"

    logger.info("Adding nutritional constraints...")
    for nutriente, limiti in TARGETS.items():
        if limiti.get('min') is not None:
            model += pulp.lpSum([pool_df.loc[i, nutriente] * quantita[i] for i in pool_df.index]) >= limiti[
                'min'], f"Min_{nutriente}"
        if limiti.get('max') is not None:
            model += pulp.lpSum([pool_df.loc[i, nutriente] * quantita[i] for i in pool_df.index]) <= limiti[
                'max'], f"Max_{nutriente}"

    logger.info("Adding variety and quantity constraints (Big-M formulation)...")
    # Questa è la formulazione "Big-M" che lega la quantità alla scelta binaria
    for i in pool_df.index:
        categoria = pool_df.loc[i, 'Categoria']
        M = MAX_KG_PER_CONDIMENTO if 'Olio' in categoria or 'Condimenti' in categoria else MAX_KG_PER_PRODOTTO_CRUDO
        # La quantità può essere > 0 SOLO SE prodotto_usato[i] è 1.
        model += quantita[i] <= M * prodotto_usato[i], f"Link_Quantita_Scelta_{i}"
        # Se un prodotto è usato, deve avere una quantità minima (evita valori infinitesimali)
        model += quantita[i] >= 0.001 * prodotto_usato[i], f"Anti_Infinetesimal_{i}"

    # Ora il vincolo sulla varietà funzionerà, perché è basato sulla variabile binaria
    model += pulp.lpSum(prodotto_usato) >= MIN_PRODOTTI_DIVERSI, "Min_Varieta"
    model += pulp.lpSum(prodotto_usato) <= MAX_PRODOTTI_DIVERSI, "Max_Varieta"
    # ### <<< FINE MODIFICHE FONDAMENTALI >>> ###

    logger.info("Adding dietary rules (category constraints)...")
    for categoria, min_kg in VINCOLI_CATEGORIA['quantita_minima_kg'].items():
        indici_categoria = pool_df[pool_df['Categoria'] == categoria].index
        if not indici_categoria.empty:
            model += pulp.lpSum(
                [quantita[i] for i in indici_categoria]) >= min_kg, f"Min_Kg_{categoria.replace(' ', '_')}"

    for nome_gruppo, dettagli in VINCOLI_CATEGORIA.get('quantita_minima_kg_gruppo', {}).items():
        lista_categorie = dettagli['categorie']
        min_kg_gruppo = dettagli['min_kg']
        indici_gruppo = pool_df[pool_df['Categoria'].isin(lista_categorie)].index
        if not indici_gruppo.empty:
            model += pulp.lpSum(
                [quantita[i] for i in indici_gruppo]) >= min_kg_gruppo, f"Min_Kg_Group_{nome_gruppo.replace(' ', '_')}"

    logger.info("Starting the solver...")
    model.solve()
    return model, quantita


def stampa_risultati(model: pulp.LpProblem, pool_df: pd.DataFrame, quantita: dict):
    status = pulp.LpStatus[model.status]
    logger.info(f"--- Phase 3: Optimization Results ---")
    logger.info(f"Solution Status: {status}")

    if status != 'Optimal':
        logger.warning("WARNING: An optimal solution was not found. Constraints may be too restrictive.")
        return

    print("\n" + "=" * 60)
    print("🍽️  OPTIMAL AND BALANCED DAILY FOOD PLAN  🍽️")
    print(f"Minimum daily cost to meet targets: {pulp.value(model.objective):.2f} €")
    print("=" * 60)

    risultati = []
    for i in pool_df.index:
        if quantita[i].varValue > 0.001:
            q_kg = quantita[i].varValue
            prodotto = {'Categoria': pool_df.loc[i, 'Categoria'], 'Nome': pool_df.loc[i, 'Nome Prodotto'],
                        'Quantità (g)': q_kg * 1000, 'Costo (€)': q_kg * pool_df.loc[i, 'Prezzo al Kg']}
            for nut in TARGETS.keys():
                prodotto[nut] = q_kg * pool_df.loc[i, nut]
            risultati.append(prodotto)

    risultati_df = pd.DataFrame(risultati).sort_values(by='Categoria')
    print(risultati_df[['Categoria', 'Nome', 'Quantità (g)', 'Costo (€)']].to_string(index=False))

    print("\n" + "-" * 60)
    print("📊  TOTAL NUTRITIONAL SUMMARY  📊")
    print("-" * 60)
    somme_nutrizionali = risultati_df.sum(numeric_only=True)
    for nut, limiti in TARGETS.items():
        valore_reale = somme_nutrizionali.get(nut, 0)
        target_str = f"(Target: {limiti['min'] or 'N/A'} - {limiti['max'] or 'N/A'})"
        print(f"{nut:<12}: {valore_reale:>7.1f} {target_str}")
    print("-" * 60)


# =========================================================================
# === 5. MAIN EXECUTION BLOCK ===

if __name__ == "__main__":
    df_prodotti = prepara_dati()

    if df_prodotti is not None and not df_prodotti.empty:
        modello_risolto, quantita_risultato = ottimizza_dieta(df_prodotti)
        stampa_risultati(modello_risolto, df_prodotti, quantita_risultato)