# Schema Wiki — Pirandello Chatbot + Wiki Manager

Questo file definisce le regole di struttura, convenzione e funzionamento per la gestione della Wiki di Pirandello. Funge da "Operating Manual" per l'agente LLM.

## 1. Architettura delle cartelle

La base di conoscenza è organizzata in tre livelli principali:

1. **Fonti Grezze (`raw/articles/`)**:
   - Contiene i testi originali (.txt, .md) caricati dall'utente.
   - Queste fonti sono **immutabili**: l'LLM le legge ma non le modifica mai.
2. **La Wiki (`wiki/pages/`)**:
   - Contiene le pagine sintetizzate in Markdown dall'LLM. È suddivisa nelle seguenti categorie:
     - `sources/` (Opere: commedie, saggi, romanzi)
     - `entities/` (Personaggi e persone reali)
     - `concepts/` (Temi chiave, concetti filosofici ed estetici)
     - `synthesis/` (Analisi trasversali e linee guida sullo stile come `pirandello-voice.md`)
     - `queries/` (FAQ e risposte pronte all'uso)
3. **Lo Schema (`LLM-WIKI.md`)**:
   - Questo file di configurazione e regole che definisce il funzionamento del sistema.

---

## 2. Convenzioni di formattazione delle pagine

Ogni pagina della Wiki deve rispettare i seguenti requisiti:

### Frontmatter YAML
Tutti i file `.md` nella Wiki devono iniziare con il frontmatter YAML standardizzato:
```yaml
---
type: source | entity | concept | synthesis | query
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [tag1, tag2]
---
```
*Nota: Il campo `type` usa sempre la forma singolare (`concept`, `entity`, `source`, `synthesis`, `query`) per coerenza.*

### Collegamenti interni (Wikilinks)
I collegamenti interni devono usare la sintassi dei **Wikilink puliti di Obsidian**, senza percorsi relativi (`../`) e senza estensione (`.md`):
- Formato: `[[nome-file-destinazione|Testo Visualizzato]]` o `[[nome-file-destinazione]]`
- Esempi: `[[mattia-pascal|Mattia Pascal]]`, `[[umorismo|Umorismo]]`, `[[il-fu-mattia-pascal|Il fu Mattia Pascal]]`.
- I nomi dei file devono essere scritti in **lowercase-kebab-case** (es. `il-fu-mattia-pascal`).

---

## 3. File Speciali di Navigazione

### index.md (Catalogo dei contenuti)
Posizionato nella radice del progetto, `index.md` è il catalogo completo di tutta la wiki. È suddiviso per categoria e contiene per ciascuna pagina:
- Il link relativo al file (`[Titolo](wiki/pages/categoria/nome-file.md)`)
- Una descrizione di una riga
- Viene aggiornato automaticamente ad ogni ingestione.

### log.md (Registro cronologico)
Posizionato nella radice del progetto, è un registro append-only delle operazioni eseguite in ordine cronologico.
- Ogni voce deve seguire il formato:
  ```markdown
  ## [YYYY-MM-DD HH:MM] operazione | Titolo/Dettaglio
  - Dettagli aggiuntivi (es. file letti, pagine modificate)
  ```

---

## 4. Operazioni Core dell'Agente

### A. Ingest (Ingestione di una fonte)
1. **Leggi la fonte**: Leggi il file da `raw/articles/` usando `source_read`.
2. **Analisi e Sintesi**: Discuti i temi chiave con l'utente.
3. **Aggiornamento/Creazione Pagine**:
   - Crea le nuove pagine in `wiki/pages/<categoria>/` usando `wiki_create`.
   - Aggiorna le pagine esistenti correlate usando `wiki_update` inserendo i nuovi collegamenti.
4. **Registrazione**:
   - Aggiungi la riga appropriata in `index.md`.
   - Appendi la registrazione nel `log.md`.

### B. Query (Risposta a domande)
1. **Ricerca**: Usa `wiki_search` per trovare le pagine wiki più pertinenti.
2. **Sintesi**: Rispondi all'utente basandoti sul contesto compilato nella Wiki.
3. **Salvataggio**: Se la risposta contiene una sintesi complessa o una spiegazione preziosa, offri all'utente di salvarla come nuova pagina in `synthesis/` o `queries/` per espandere permanentemente la Wiki.

### C. Lint (Verifica dello stato di salute)
Controlla periodicamente lo stato della Wiki cercando:
- **Broken Links**: Collegamenti a file non esistenti.
- **Orphan Pages**: Pagine che non ricevono link da nessun'altra pagina della Wiki.
- **Inconsistenze**: Campi frontmatter mancanti o scorretti.
- **Formato Link Errato**: Collegamenti che contengono `../` o `.md` all'interno delle parentesi `[[...]]`.
