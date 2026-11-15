# plantschema

Anlagen-neutrale semantische Anlagen-Schemas (YAML) → **deterministisches
P&ID-SVG** mit hartem **Kollisions-Gate** im Build. Eine YAML-Datei
beschreibt die Anlage (Komponenten, Leitungen, Fühler/Readouts, Labels);
der Generator rendert daraus ein byte-deterministisches SVG mit stabilen
Element-IDs (`comp-*`, `pipe-*`, `readout-*`, `lbl-*`) — zum Einbetten in
UIs mit Live-Readout- und Flow-Animation-Hooks. First-Target (S4): das
cmi-Gesamt-Schema (V6.3).

## Quickstart

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# Parse + Validate (kein Artefakt)
.venv/bin/python -m plantschema load --in tests/fixtures/minimal/installation.yaml

# Pipeline + SVG-Write (Kollisions-Gate aktiv)
.venv/bin/python -m plantschema render \
    --in tests/fixtures/minimal/installation.yaml \
    --out tmp/minimal.svg

# Nur Gate-Check (kein Write), z. B. für CI
.venv/bin/python -m plantschema check --in tests/fixtures/minimal/installation.yaml
```

## Projekt-Layout

```
plantschema/
├── plantschema/          # Paket: Modell + Pipeline-Module
│   ├── model.py          #   Pydantic-v2-Modelle (Schema, Component, Pipe, …)
│   ├── io.py             #   YAML → Modell (SchemaError mit Zeilenreferenz)
│   ├── validate.py       #   Referenz-/Typ-Checks (Problemliste)
│   ├── symbols.py        #   Port-Geometrie-Katalog + S1-Platzhalter-Symbole
│   ├── route.py          #   Pipe-Geometrie (via-Route 1:1 / Manhattan-Fallback)
│   ├── place.py          #   Readout-/Label-Positionen
│   ├── qa.py             #   Kollisions-Detektion (TEXT×TEXT, LINE×TEXT)
│   ├── emit.py           #   SVG-Dokument-Bau (byte-deterministisch)
│   └── __main__.py       #   CLI: load | validate | render | check
├── tests/                # pytest (Fixtures: minimal, invalid, colliding)
└── docs/
    └── model-reference.md  # Semantisches Modell + Kanon (maschinell prüfbar)
```

## CLI + Gate-Exit-Codes

| Befehl | Bedeutung | Exit |
|---|---|---|
| `load --in X.yaml` | Parse + Validate, kein Artefakt | 0 / 2 / 4 |
| `validate --in X.yaml` | dito | 0 / 2 / 4 |
| `render --in X.yaml --out Y.svg` | Pipeline + SVG-Write + Gate | 0 / 2 / 3 / 4 |
| `check --in X.yaml` | Pipeline in-memory + nur Gate-Report | 0 / 2 / 3 |

- **0** = ok · **2** = Schema-/Validierungsfehler (je Problem eine
  Stderr-Zeile: `[line N] path: message`) · **3** = Gate-Fehler
  (je Kollision eine Zeile) · **4** = IO-Fehler (Datei fehlt, YAML
  unlesbar/ungültig).
- `--no-gate` (nur `render`/`check`): Kollisions-Gate aus (Debug).

## Wie läuft der Build (Determinismus)

Gleiche Eingabe → **byte-identische** SVG (Test: 2× render → identische
sha256). Regeln:

- Kein Zeitstempel, keine Zufalls-IDs im Artefakt.
- Festes Attribut-Reihenfolge (Insertion-Order), keine Iteration über
  unsortierte Sammlungen.
- Element-Reihenfolge = Schema-Reihenfolge (Komponenten/Pipes/Readouts/
  Labels), Layer-Reihenfolge: Hintergrund → Pipes → Komponenten →
  Readouts → Labels.
- Stabile IDs: `comp-<id>`, `pipe-<id>`, `readout-<id>`, `lbl-<id>`
  (UI-Bindungsvertrag, s. `docs/model-reference.md`).
