import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re


def pulisci_numero(testo):
    """Estrae solo i numeri da una stringa (es: '240.000 €' -> 240000)."""
    if not testo: return 0
    num = re.sub(r'\D', '', testo)
    return int(num) if num else 0


def avvia_scraping(pagine=3):
    # Configurazione browser
    options = uc.ChromeOptions()
    # options.add_argument('--headless') # Decommenta per non vedere il browser

    driver = uc.Chrome(options=options, version_main=148)
    risultati = []

    print(f"🚀 Avvio scraping di {pagine} pagine...")

    try:
        for p in range(1, pagine + 1):
            # URL corretto per la paginazione su Idealista
            url = f"https://www.idealista.it/geo/vendita-case/toscana/con-dimensione-max_100,aste_no,senza-inquilini,alta-efficienza/lista-{p}.htm"

            print(f"\n--- 📄 Caricamento Pagina {p} ---")
            driver.get(url)

            # Gestione intelligente delle pause
            if p == 1:
                # Pausa manuale obbligatoria solo alla prima pagina
                print("⏸️ PRIMA PAGINA: Accetta i cookie, chiudi i banner e risolvi eventuali captcha.")
                input("👉 Quando la pagina è pronta e pulita, premi INVIO qui per far partire l'automazione...")
            else:
                # Dalla seconda pagina procede da solo senza blocchi
                attesa = random.uniform(7.2, 12.5)
                print(f"⏳ Pausa umana automatica di {attesa:.1f} secondi...")
                time.sleep(attesa)

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            annunci = soup.find_all('article', class_='item')

            for annuncio in annunci:
                try:
                    # 1. ID Annuncio
                    id_annuncio = annuncio.get('data-element-id')

                    # 2. Titolo e Località
                    titolo_tag = annuncio.find('a', class_='item-link')
                    if not titolo_tag: continue

                    titolo_testo = titolo_tag.get_text(strip=True)
                    full_title_attr = titolo_tag.get('title', "")

                    # Estraiamo la località
                    parti_titolo = full_title_attr.split(',')
                    localita = parti_titolo[-1].strip() if len(parti_titolo) > 1 else "Toscana"

                    # 3. Prezzo
                    prezzo_tag = annuncio.find('span', class_='item-price')
                    prezzo = pulisci_numero(prezzo_tag.text) if prezzo_tag else 0

                    # 4. Caratteristiche (Locali e Mq)
                    dettagli = annuncio.find_all('span', class_='item-detail')
                    locali = 0
                    mq = 0
                    for d in dettagli:
                        testo_d = d.get_text().lower()
                        if 'locali' in testo_d or 'locale' in testo_d:
                            res = re.search(r'\d+', testo_d)
                            locali = int(res.group()) if res else 0
                        if 'm2' in testo_d:
                            res = re.search(r'\d+', testo_d)
                            mq = int(res.group()) if res else 0

                    # 5. Aggiunta dati alla lista
                    if mq > 0:
                        risultati.append({
                            'ID': id_annuncio,
                            'Titolo': titolo_testo,
                            'Localita': localita,
                            'Prezzo': prezzo,
                            'Locali': locali,
                            'Mq': mq,
                            'Prezzo_Mq': round(prezzo / mq) if prezzo > 0 else 0
                        })
                except Exception as e:
                    print(f"❌ Errore nell'estrazione di un annuncio: {e}")
                    continue

            print(f"✅ Estratti {len(annunci)} annunci dalla pagina {p}")

        # Salvataggio Finale
        if risultati:
            df = pd.DataFrame(risultati)
            df.to_csv("dati_idealista_toscana.csv", index=False, encoding='utf-8-sig')
            df.to_excel("dati_idealista_toscana.xlsx", index=False)
            print(f"\n💾 Scraping completato! {len(df)} immobili salvati in CSV ed Excel.")
        else:
            print("\n❌ Nessun dato estratto. Controlla se il sito ti ha bloccato.")

    except Exception as e:
        print(f"🚨 Errore fatale: {e}")

    finally:
        try:
            driver.quit()
        except OSError:
            # Ignoriamo silenziosamente il WinError 6 di undetected_chromedriver
            pass


if __name__ == "__main__":
    avvia_scraping(pagine=60)