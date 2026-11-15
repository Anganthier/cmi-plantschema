# Model-Reference — plantschema/v1 (Kanon)

> **Status:** S2-Kanon (maschinell prüfbar; S1-Regeln unverändert, wo
> nicht anders gekennzeichnet). Kurze Regeln mit ID-Referenz;
> **M** = muss (hart), **S** = sollte, **K** = kann. Abweichungen → HITL.
> Neue Regeln werden als R-Nummern **ergänzt**, bestehende nicht
> umbrochen (R-1…R-28 = S1, R-29 ff. = S2).

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
  Manhattan-Fallback (horizontal-dann-vertikal, 1 Umrisspunkt; S3:
  Kanal-Hinweis/Vermeidungslogik, wenn das Kollisions-Gate den Fallback
  bewertet). Die Punktesequenz (`PipeGeometry.points`) ist stabile
  API für das S3-Gate (LINE×TEXT-Segmente).

## 5. P&ID-Symbole + Port-Geometrie-Katalog (S2, Seed cmi)

**Symbole (Kanon):** 18 P&ID-Symbole als `<g id="pid-…">` im emittierten
`<defs>` (klassen-basiert `.pid`/`.pid-t`, **byte-identisch portiert**
aus cmi `ui/svg/pid-symbols.svg` — DIN EN ISO 10628-1 + branchenübliche
Haustechnik-Symbole; cmi-Demo-Block `pid-demo` wird NICHT portiert):
`pid-tank-buffer`, `pid-boiler-oil`, `pid-boiler-solid`,
`pid-collector-solar`, `pid-heatex-plate`, `pid-heatex-shell`,
`pid-mixing`, `pid-pump-cent`, `pid-valve-2way`, `pid-valve-3way`,
`pid-valve-globe`, `pid-valve-actuator`, `pid-throttle`, `pid-radiator`,
`pid-tap`, `pid-chimney`, `pid-pt`, `pid-flow-switch`.

- **R-12 (S→M, S2)** Komponententypen mit bekanntem Symbol werden per
  `<use href="#pid-…">` (x/y = `at`, Symbol (0,0)-zentriert) gerendert,
  `data-symbol="pid-…"`; unbekannter Typ → S1-Platzhalter-Rect
  (`data-symbol="placeholder"`; Problem `unknown-type` in validate).
- **R-29 (M, S2) Pfeil-Endpunkt-Regel:** kein `marker-end` (Marker-Farbe
  aus `context-stroke` nicht portabel, 1 generischer Marker genügt nicht
  für alle Kind-Farben) → stattdessen **Pfeil-Endpunkt = kleines
  Dreieck-Path am Pipe-Ende** (`<path class="pipe-arrow arrow-<kind>">`,
  Fill = Kind-Farbe; Spitze exakt am Pipe-Endpunkt, Basis 10 px davor,
  Breite ±4 px, rotiert nach Letztem-Segment-Vektor; degenerierte Pipe
  < 2 Punkte: kein Pfeil). Der S1-Marker `#arrow` bleibt im `<defs>`
  (Kontinuität), wird aber nicht mehr von Pipes referenziert.
- **R-30 (M, S2) Port-Endpunkt-Regel (S4N-2-QA):** Pipe-Endpunkte treffen
  **exakt** auf Port-Positionen (absolut = `comp.at` + Port-Offset).
  Port-Offsets = **Stiel-Enden** des cmi-Symbols (Stiele bei ±20 px);
  bei Symbolen ohne Prozess-Stiel = **Kanten-Mitte** (Tank-Geometrie
  nach cmi `loop-svg.js`-Kommentar-Kanon: x=±30, y=±60; Zone-Linien
  y=±20; Kessel: Rect-Kante).
- **R-11 (M)** Ports ohne Achse-Definition: Readout-Offset in Richtung des
  Offsets; Offset (0,0) → nach oben (S1-Default).

`at` = **Zentrum** des Symbols. Port-Offset = relative Position; Achse =
Ausrichtung für Readout-Offset + Pipe-Anbindung.

| Typ | Ports (dx, dy, Achse) |
|---|---|
| `tank-buffer` | `top` (0,−60, up) · `mid-top` (0,−20, up) · `mid-bottom` (0,+20, down) · `bottom` (0,+60, down) · `left` (−30,0, left) · `right` (+30,0, right) |
| `boiler-oil` | `top` (0,−26, up) · `left` (−28,0, left) · `right` (+28,0, right) · `bottom` (0,+26, down) |
| `boiler-solid` | `top` (0,−30, up) · `left` (−28,0, left) · `right` (+28,0, right) · `bottom` (0,+20, down) |
| `collector-solar` | `in` (−41,0, left) · `out` (+41,0, right) |
| `heatex-plate` | `in` (−35,0, left) · `out` (+35,0, right) · `top` (0,−14, up) · `bottom` (0,+14, down) |
| `heatex-shell` | `in` (−30,0, left) · `out` (+30,0, right) · `bottom` (0,+20, down) |
| `mixing` | `in` (−14,0, left) · `out` (+14,0, right) · `top` (0,−14, up) · `bottom` (0,+14, down) |
| `pump` | `in` (−20,0, left) · `out` (+20,0, right) |
| `valve-2way` | `in` (−20,0, left) · `out` (+20,0, right) · `stem` (0,−20, up) |
| `valve-3way` | `in` (−20,0, left) · `out` (+20,0, right) · `mix` (0,+20, down) |
| `valve-globe` | `in` (−20,0, left) · `out` (+20,0, right) · `stem` (0,−20, up) |
| `valve-actuator` | `in` (−20,0, left) · `out` (+20,0, right) · `stem` (0,−20, up) |
| `throttle` | `in` (−20,0, left) · `out` (+20,0, right) · `stem` (0,−20, up) |
| `radiator` | `in` (−30,0, left) · `out` (+30,0, right) |
| `tap` | `in` (−14,0, left) · `out` (+14,0, right) · `draw` (0,+20, down) |
| `chimney` | `left` (−9,0, left) · `right` (+9,0, right) · `bottom` (0,+34, down) |
| `pt`, `flow-switch` | keine Pipe-Ports (nur Readout-Hosts, `x/y`-Referenz) |

- **R-31 (S, S2) Typ→Symbol-Mapping:** 1:1 (`tank-buffer` →
  `pid-tank-buffer` …, `pump` → `pid-pump-cent`); Alias `valve` =
  2-Wege-Default (`pid-valve-2way` + valve-2way-Geometrie);
  `valve-3way`, `valve-globe` direkt. Label-Offset je Typ:
  `symbols.LABEL_OFFSET` (halbe Symbolhöhe + 12 px; Default 32) —
  Labels stehen **oben über dem Symbol** (`.txt-h` + sub `.txt-s`,
  Kollisions-Prüfung: S3).

## 6. Readout

| Feld | Typ | Pflicht |
|---|---|---|
| `id` | string (R-3) | M |
| `at` | `{ comp, port }` **oder** `{ x, y }` (exklusiv) | M |
| `label` | string | M |
| `value_key` | string | K (→ `data-value-key`) |
| `loop` | string | K (→ `data-loop`) |
| `side` | `left\|right` (default `right`, S2) | K |

- **R-13 (M)** comp-Referenz: Komponente + Port müssen existieren
  (sonst `ref-component`/`ref-port`). `pt`/`flow-switch` sind **keine**
  Pipe-Port-Hosts.
- **R-14 (M)** `{x,y}`: Koordinaten im Canvas (x ≤ width, y ≤ height).
- **R-15 (S1, S2)** Position bei comp-Referenz = Port-Position + **16 px**
  außerhalb in Port-Achsenrichtung (`place.PLACE_OUTER`); x/y = Passthrough.
  S2-Emissions-Struktur (cmi `loop-svg.js::readout`): PT-Symbol
  `<use href="#pid-pt">` an der Position + **Wert-Text** `.ro-val`
  (Platzhalter „–", 12 px, `data-value="true"`-Hook) + **Label-Text**
  `.ro-lbl` (11 px) — Wert oben (y − 2), Label unten (y + 14), 16 px
  neben dem Symbol: `side=right` (Default) → rechts, `text-anchor=start`;
  `side=left` → links, `text-anchor=end`.

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
| `<defs>` | `#arrow` + `#pid-…` (18 Symbole) | P&ID-Katalog (S2, byte-identisch cmi-Seed); Symbol-IDs sind Referenz-Ziele, keine Artefakt-Elemente |
| Komponente | `g[@id="comp-<id>"]` | + `data-type`, `data-loop` (falls gesetzt), `data-flow` (falls `flow`), `data-symbol="pid-…"` (bekannt) bzw. `data-symbol="placeholder"` (S1-Fallback); Inhalt: `<use href="#pid-…">` (x/y = at) + Label-Texte `.txt-h`/`.txt-s` oben (R-31) |
| Pipe | `path[@id="pipe-<id>"]` | + `data-kind`, `data-flow` (falls `flow`), `class="pipe <kind>"`; **kein** `marker-end` (S2, R-29) |
| Pfeil-Endpunkt | `path[@class="pipe-arrow arrow-<kind>"]` | Kleines Dreieck am Pipe-Ende (S2, R-29), Fill = Kind-Farbe |
| Readout | `g[@id="readout-<id>"]` | + `data-value-key` (falls gesetzt), `data-readout` = Label-Text, `data-loop` (falls gesetzt); Inhalt: `<use href="#pid-pt">` + Wert `.ro-val` (`data-value="true"`) + Label `.ro-lbl` (cmi-Kanon; `side` → `text-anchor`, R-15) |
| Label | `text[@id="lbl-<id>"]` | + `text-anchor`, `class="txt"` |
| Layer | `layer-pipes`, `layer-components`, `layer-readouts`, `layer-labels` | Reihenfolge = Z-Order (R-2) |

- **R-21 (M)** IDs sind deterministisch aus `id` abgeleitet (Präfixe
  `comp-`/`pipe-`/`readout-`/`lbl-`) — UI-Bindungsvertrag (cmi S4N-3:
  Readout-Werte + Flow-Animation per ID anbinden; CSS/JS bleibt cmi-seitig).

**ALC-Änderung (S2):** Output-Format geändert — Komponenten werden statt
S1-Platzhalter-Rects per P&ID-`<use>` (Seed cmi `ui/svg/pid-symbols.svg`)
gerendert, `data-symbol` trägt jetzt die Symbol-ID; Pipes tragen keine
`marker-end` mehr (Pfeil-Endpunkte = `.pipe-arrow`-Paths, R-29);
Readouts haben jetzt PT-Symbol + `.ro-val`/`.ro-lbl` (statt S1-Label-
Text `.txt`); Style-Block enthält cmi-V6.3-Klassen (`.pid`, `.pid-t`,
`.ro-val`, `.ro-lbl`, `.txt-h`, `.txt-s`, `.pipe` stroke-width 3,
`.ctl` gestrichelt). Layer-Z-Order + ID-Verträge unverändert.

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
  S2-Input: Readout-Texte = `.ro-val` (12 px) + `.ro-lbl` (11 px) mit
  Emissions-Position/Anker (`side`); Labels = `.txt`.
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
