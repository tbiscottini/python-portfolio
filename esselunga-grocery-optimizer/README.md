\# Esselunga Grocery Optimizer: Una Pipeline di Dati End-to-End



Questo progetto è una pipeline di dati completa progettata per risolvere il problema dell'ottimizzazione di una spesa alimentare. Il sistema estrae, pulisce e analizza i dati di oltre 17.000 prodotti dal sito di Esselunga, per poi utilizzare algoritmi di ottimizzazione per trovare il paniere di prodotti a costo minimo che rispetta complessi vincoli nutrizionali.



\## Struttura del Progetto



La pipeline è suddivisa in moduli logici:



1\.  \*\*Data Sourcing \& Extraction (`esselunga\_full\_scraper.py`):\*\*

&nbsp;   \*   Gestisce l'autenticazione della sessione tramite \*\*Selenium\*\*.

&nbsp;   \*   Estrae i dati dei prodotti in modo performante utilizzando \*\*multithreading\*\* e chiamate API dirette.

&nbsp;   \*   Implementa una logica robusta di gestione degli errori, inclusi i `rate limit` (HTTP 429).



2\.  \*\*Data Transformation \& Cleaning:\*\*

&nbsp;   \*   Utilizza \*\*Pandas\*\* per un'intensa attività di pulizia, normalizzazione e feature engineering.

&nbsp;   \*   Implementa una logica di normalizzazione avanzata per standardizzare le etichette nutrizionali eterogenee.



3\.  \*\*Optimization (`nuovo\_paniere.py`):\*\*

&nbsp;   \*   Utilizza la libreria \*\*PuLP\*\* per definire e risolvere un problema di \*\*Programmazione Lineare\*\*.

&nbsp;   \*   L'algoritmo trova la combinazione di prodotti a costo minimo che soddisfa un set di vincoli giornalieri (calorie, proteine, grassi, fibre, ecc.) e regole di composizione del paniere (es. "almeno 200g di verdura").



\## Tecnologie Utilizzate

\- \*\*Python\*\*

\- \*\*Data Engineering:\*\* Pandas, NumPy, Selenium, BeautifulSoup, concurrent.futures

\- \*\*Operations Research:\*\* PuLP (Linear Programming)

\- \*\*Altro:\*\* Requests, Logging

