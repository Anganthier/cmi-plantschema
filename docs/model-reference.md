# Model-Reference — plantschema/v1 (Kanon)

> **Status:** S1-Kanon (maschinell prüfbar). Kurze Regeln mit ID-Referenz;
> **M** = muss (hart), **S** = sollte, **K** = kann. Abweichungen → HITL.

## 1. Schema-Root

```yaml
schema: plantschema/v1            # M: exakt diese Zeichenkette (Field `version`, Alias `schema`)
canvas: { width: 2200, height: 1500, background: "#0b1220" }
components: [ … ]                 # optional (default [])
pipes: [ … ]
readouts: [ … ]
labels: [ … ]
```

- **R-1 (M)** Unbekannte Keys auf beliebiger Ebene → Schema-Fehler
  (`extra=forbid`).
- **R-2 (M)** Alle Listen in der Reihenfolge emittiert (deterministisch).

## 2. IDs + Koordinaten

- **R-3 (M)** `id` ∈ `[A-Za-z0-9][A-Za-z0-9._-]*` — keine Whitespace,
  keine Sonderzeichen, keine Leerzeichen-Schreibweise (z. B. `oel-` statt
  `öl-`/`oel `).
- **R-4 (M)** `at`/`via` = genau 2 Zahlen, ganzzahlig, `≥ 0`
  (Pydantic-Validator). SVG y-Achse: nach **unten**.
- **R-5 (M)** IDs sind über **alle** Arten eindeutig
  (component + pipe + readout + label, einer Menge) → Problem `dup-id`.

## 3. Component

| Feld | Typ | Pflicht |
|---|---|---|
| `id` | string (R-3) | M |
| `type` | string, Katalog §5 | M |
| `at` | `[x, y]` (Zentrum, R-4) | M |
| `label` | `{ text, sub? }` | K |
| `ports` | list[string] (Override) | K |
| `loop` | string | K (→ `data-loop`) |
| `flow` | string | K (→ `data-flow`) |

- **R-6 (M)** `type` muss im S1-Katalog bekannt sein → `unknown-type`.
- **R-7 (M)** `ports`-Override: nur Port-Namen aus dem Typ-Katalog erlaubt;
  wenn gesetzt, dürfen **nur** diese Ports von Pipes/Readouts belegt werden.

## 4. Pipe

| Feld | Typ | Pflicht |
|---|---|---|
| `id` | string (R-3) | M |
| `from` | `{ comp, port }` | M |
| `to` | `{ comp, port }` | M |
| `kind` | `vl\|rl\|ww\|gas\|ctl` | M |
| `via` | list[`[x,y]`] (Autor-Route) | K |
| `flow` | string | K (→ `data-flow`) |

- **R-8 (M)** `from`/`to.comp` existiert → sonst `ref-component`.
- **R-9 (M)** `from`/`to.port` liegt im (Override-geprägten) Port-Set des
  Komponententyps → sonst `ref-port`.
- **R-10 (S)** `via` = autorisierte Route, 1:1 übernommen; ohne `via` =
  Manhattan-Fallback (horizontal-dann-vertikal, 1 Umrisspunkt; S2:
  Kanal-Hinweis-Logik).

## 5. Port-Geometrie-Katalog (S1-Platzhalter)

`at` = **Zentrum** des Symbols. Port-Offset = relative Position; Achse =
Richtung, in der ein Readout-Label außerhalb des Ports steht.

| Typ | Ports (dx, dy, Achse) |
|---|---|
| `tank-buffer` | `top` (0,−60, up) · `mid` (0,0, up) · `bottom` (0,+60, down) · `left` (−30,0, left) · `right` (+30,0, right) |
| `boiler-oil` | `top` (0,−26, up) · `left` (−28,0, left) · `right` (+28,0, right) · `bottom` (0,+26, down) |
| `boiler-solid` | `top` (0,−30, up) · `left` (−28,0, left) · `right` (+28,0, right) · `bottom` (0,+30, down) |
| `pump` | `in` (−20,0, left) · `out` (+20,0, right) |
| `valve-2way` | `in` (−20,0, left) · `out` (+20,0, right) |
| `heatex-plate` | `in` (−35,0, left) · `out` (+35,0, right) · `top` (0,−14, up) · `bottom` (0,+14, down) |
| `radiator` | `in` (−30,0, left) · `out` (+30,0, right) |
| `collector-solar` | `in` (−34,0, left) · `out` (+34,0, right) |
| `chimney` | `bottom` (0,+34, down) |
| `tap` | `in` (0,−7, up) |
| `pt`, `flow-switch` | keine Pipe-Ports (nur Readout-Hosts, `x/y`-Referenz) |

- **R-11 (M)** Ports ohne Achse-Definition: Readout-Offset in Richtung des
  Offsets; Offset (0,0) → nach oben (S1-Default).
- **R-12 (S)** S1-Zeichnungen = schlichte Platzhalter (Rect/Kreis/Pfadsymbol),
  `data-symbol="placeholder"`; S2 portiert die P&ID-`<defs>` aus cmi
  `ui/svg/pid-symbols.svg` (DIN EN ISO 10628-1) — Port-Katalog bleibt Kanon.

## 6. Readout

| Feld | Typ | Pflicht |
|---|---|---|
| `id` | string (R-3) | M |
| `at` | `{ comp, port }` **oder** `{ x, y }` (exklusiv) | M |
| `label` | string | M |
| `value_key` | string | K (→ `data-value-key`) |
| `loop` | string | K (→ `data-loop`) |

- **R-13 (M)** comp-Referenz: Komponente + Port müssen existieren
  (sonst `ref-component`/`ref-port`). `pt`/`flow-switch` sind **keine**
  Pipe-Port-Hosts.
- **R-14 (M)** `{x,y}`: Koordinaten im Canvas (x ≤ width, y ≤ height).
- **R-15 (S1)** Position bei comp-Referenz = Port-Position + **16 px**
  außerhalb in Port-Achsenrichtung (`place.PLACE_OUTER`); x/y = Passthrough.

## 7. Label

| Feld | Typ | Pflicht |
|---|---|---|
| `id` | string (R-3) | M |
| `at` | `[x, y]` (R-4) | M |
| `text` | string | M |
| `anchor` | `start\|middle\|end` (default `start`) | K |

- **R-16 (M)** `at` im Canvas (x ≤ width, y ≤ height).
- **R-17 (S1)** Position = exakt `at`; Auto-Slot-Regeln kommen in S3
  (Slot um Host + Mindestabstand 8 px).

## 8. Canvas

- **R-18 (M)** `width`/`height` > 100 (sonst `canvas-too-small`).
- **R-19 (S)** `background` = hex-Farbe (default `#0b1220`); emittiert als
  `<rect id="canvas-bg">` unterste Ebene.

## 9. Validierung (S1-Problem-Codes)

| Code | Prüfung |
|---|---|
| `dup-id` | ID mehr als einmal (alle Arten, R-5) |
| `ref-component` | Pipe/Readout zeigt auf fehlende Komponente (R-8, R-13) |
| `ref-port` | Pipe/Readout-Port nicht im (Override-geprägten) Port-Set (R-9, R-13) |
| `out-of-canvas` | Readout/Label außerhalb des Canvas (R-14, R-16) |
| `canvas-too-small` | width/height ≤ 100 (R-18) |
| `unknown-type` | Komponententyp nicht im Katalog (R-6) |

- **R-20 (M)** `validate` liefert **alle** Probleme (nicht nur das erste);
  CLI gibt je Problem eine Zeile aus und exitet 2.

## 10. SVG-Vertrag (stabile IDs + data-Attribute)

| Element | ID / Attribut | Bedeutung |
|---|---|---|
| Komponente | `g[@id="comp-<id>"]` | + `data-type`, `data-loop` (falls gesetzt), `data-flow` (falls `flow`), `data-symbol="placeholder"` (S1) |
| Pipe | `path[@id="pipe-<id>"]` | + `data-kind`, `data-flow` (falls `flow`), `marker-end="url(#arrow)"`, `class="pipe <kind>"` |
| Readout | `g[@id="readout-<id>"]` | + `data-value-key` (falls gesetzt), `data-readout` = Label-Text, `data-loop` (falls gesetzt) |
| Label | `text[@id="lbl-<id>"]` | + `text-anchor`, `class="txt"` |
| Layer | `layer-pipes`, `layer-components`, `layer-readouts`, `layer-labels` | Reihenfolge = Z-Order (R-2) |

- **R-21 (M)** IDs sind deterministisch aus `id` abgeleitet (Präfixe
  `comp-`/`pipe-`/`readout-`/`lbl-`) — UI-Bindungsvertrag (cmi S4N-3:
  Readout-Werte + Flow-Animation per ID anbinden; CSS/JS bleibt cmi-seitig).

## 11. Determinismus (Kanon)

- **R-22 (M)** Gleiche Eingabe → byte-identische SVG (Test: 2× `render`
  → identische sha256).
- **R-23 (M)** Kein Zeitstempel, keine Zufalls-IDs im Artefakt.
- **R-24 (M)** Festes Attribut-Reihenfolge (Insertion-Order); keine
  Iteration über unsortierte Sammlungen (dict-Order ≠ deterministisch).
- **R-25 (M)** Layer-Z-Order: Hintergrund → Pipes → Komponenten → Readouts
  → Labels (jeweils in Schema-Reihenfolge).

## 12. Kollisions-Gate (S1)

- **R-26 (M)** Gate-Prüfungen S1: **TEXT×TEXT** (Bounding-Box-
  Intersektion, cmi-Heuristik: width ≈ font_size·0.52·len, Höhe ≈
  font_size·1.2) + **LINE×TEXT** (Pipe-Segment läuft durch Text-BBox,
  Sampling 5 px, ≥ 2 Treffer). S3 ergänzt TEXT×Box-Kante + USE×TEXT.
- **R-27 (M)** Kollision → exit 3 + Report (je Kollision eine Zeile:
  `KIND [elemA] × [elemB] @ (x,y) — Hinweis`); `--no-gate` = Debug-Aus.
- **R-28 (S)** Readout-/Label-Größen: Wert ≥ 12 px, Label ≥ 11 px
  (`place.VALUE_FONT_MIN`/`LABEL_FONT_MIN`; S1 emittiert 14/11 px).

## 13. Exit-Codes (CLI-Kanon)

| Exit | Bedeutung |
|---|---|
| 0 | ok |
| 2 | Schema-/Validierungsfehler (Stderr: `[line N] path: message`) |
| 3 | Gate-Fehler (Kollisionen, je Kollision eine Zeile) |
| 4 | IO-Fehler (Datei fehlt, unlesbar, ungültiges YAML) |
