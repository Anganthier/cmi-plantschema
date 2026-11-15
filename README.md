# plantschema

Anlagen-neutrale semantische Anlagen-Schemas (YAML) → **deterministisches
P&ID-SVG** mit hartem **Kollisions-Gate** im Build. Eine YAML-Datei
beschreibt die Anlage (Komponenten, Leitungen, Fühler/Readouts, Labels);
der Generator rendert daraus ein byte-deterministisches SVG mit stabilen
Element-IDs (`comp-*`, `pipe-*`, `readout-*`, `lbl-*`) — zum Einbetten in
UIs mit Live-Readout- und Flow-Animation-Hooks. First-Target (S4): das
cmi-Gesamt-Schema (V6.3).

**Symbole: P&ID-Bibliothek (18, DIN EN ISO 10628-1, Seed aus cmi)** —
`plantschema/symbols.py` portiert die `<defs>`-Symbole aus cmi
`ui/svg/pid-symbols.svg` byte-identisch (klassen-basiert `.pid`/`.pid-t`);
Komponenten werden per `<use href="#pid-…">` gerendert (Port-Endpunkte =
Stiel-Enden/Kanten-Mitte, s. `docs/model-reference.md` § 5, R-30).

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

# Rich-Beispiel (alle 18 Komponententypen, Pipes je kind, S4-Seed)
.venv/bin/python -m plantschema render \
    --in tests/fixtures/rich/installation.yaml \
    --out tmp/rich.svg
```

## Projekt-Layout

```
plantschema/
├── plantschema/          # Paket: Modell + Pipeline-Module
│   ├── model.py          #   Pydantic-v2-Modelle (Schema, Component, Pipe, …)
│   ├── io.py             #   YAML → Modell (SchemaError mit Zeilenreferenz)
│   ├── validate.py       #   Referenz-/Typ-Checks (Problemliste)
│   ├── symbols.py        #   P&ID-Symbol-Bibliothek (18 Symbole, Seed cmi)
│   │                     #   + Port-Katalog + Component-Renderer (<use>)
│   ├── route.py          #   Pipe-Geometrie (via-Route 1:1 / Manhattan-Fallback)
│   ├── place.py          #   Readout-/Label-Positionen (Slot-Regeln R-32/R-33)
│   ├── qa.py             #   Kollisions-Detektion (S3-Check-Set, R-34)
│   ├── emit.py           #   SVG-Dokument-Bau (byte-deterministisch)
│   └── __main__.py       #   CLI: load | validate | render | check
├── tests/                # pytest (Fixtures: minimal, invalid, colliding, rich)
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

## Gate-Report (R-34-Format)

Beim `check`/`render` (Gate aktiv) erscheint auf Stderr zuerst der
**Warnungs-Block** (S3-Slot-Fallbacks, R-33 — Exit bleibt **0**), dann der
**Kollisions-Block** (exit **3**); bei 0 Kollisionen kein Block:

```text
$ python -m plantschema check --in tests/fixtures/rich/installation.yaml
2 Warnung(en):
  SLOT-FALLBACK  [comp-o3_mischer.lbl] @ comp-o3_mischer (up) — alle 4 Slots kollidieren → up-Fallback (R-33)
  SLOT-FALLBACK  [comp-w_platten.lbl] @ comp-w_platten (up) — alle 4 Slots kollidieren → up-Fallback (R-33)
# (Exit 0 — Warnungen ≠ Fehler; Rich-Fixture: 0 Kollisionen)

$ python -m plantschema check --in tests/fixtures/colliding/text-box.yaml
1 Kollision(en):
  TEXT-BOX-EDGE  [lbl-lbl-tank-text] × [comp-puffer] @ (417,288) — Text 'Tank-Text' zu 92 % in der Symbol-BBox (Schwelle 50 %, R-34)
# (Exit 3)

$ python -m plantschema check --in tests/fixtures/colliding/symbol-text.yaml
1 Kollision(en):
  SYMBOL-TEXT  [readout-a1.val] × [comp-p1] @ (416,288) — Text '–' zu 64 % in der Symbol-BBox (Schwelle 50 %, R-34)
# (Exit 3)
```

Check-Arten: `text-text`, `line-text`, `text-box-edge` / `symbol-text`
(> 50 % Text-Fläche-Overlap gegen `SYMBOL_BOUNDS`), `readout-size`
(s. `docs/model-reference.md` R-34 + SYMBOL_BOUNDS-Katalog).

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
