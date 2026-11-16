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
groups: [ … ]                     # optional (default [], S4-L1, R-35)
lanes: [ … ]                      # optional (default [], S4-L5b, R-39)
readouts: [ … ]
labels: [ … ]
hidden_kinds: [ ctl ]             # optional (default [], S4-L5c, R-41)
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
| `at` | `[x, y]` (Zentrum, R-4) | K (S4-L2/R-36: Default `None` — Mitglied EINER Gruppe → Engine-Placement; sonst `component-placement-missing`) |
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
- **R-10 (S)** `via` = autorisierte Route, 1:1 übernommen (Autor-
  Override gewinnt immer, S4-L3/R-37); ohne `via` = Manhattan-Fallback
  (horizontal-dann-vertikal, 1 Umrisspunkt) + S4-L3-Kanal-Regel
  (R-37: gruppen-bewusstes Umleiten bei inter-gruppiger Fremdkreuzung,
  nur ohne `via`). Die Punktesequenz (`PipeGeometry.points`) ist
  stabile API für das Kollisions-Gate (LINE×TEXT-Segmente).

## 4b. Group (S4-L1, R-35)

| Feld | Typ | Pflicht |
|---|---|---|
| `id` | string (R-3) | M |
| `label` | string (Box-Beschriftung) | K |
| `kind` (S4-L5a, R-38) | `atomic` (Default) \| `composite` | K |
| `members` | list[string] (Component-IDs, R-3); Default `[]` (composite: leer) | M (atomic) |
| `includes` (S4-L5a, R-38) | list[string] (Group-IDs atomarer Gruppen, R-3); nur composite | M (composite) |
| `hub` | string (Component-ID, R-3) | K |
| `order` (S4-L2, R-36) | list[string] (Member-IDs; Permutation von `members`) | K |
| `hub_at` (S4-L2, R-36) | `[x, y]` Hub-Anker (Default: Box-Mitte) | K |
| `at` | `[x, y]` obere linke Ecke der Box (R-35: > 0) | M |
| `size` | `[bw, höhe]` Box-Breite/Höhe (R-35: > 0) | M |
| `frame` (S4-L5c, R-38) | bool; Default `None` = atomic **an**, composite **aus** | K |

- **R-35 (M, S4-L1) Group-Modell + Makro-Geometrie:** Makro-Gruppen
  gehören ins YAML (plant-neutral, David-Entscheidung S4).
  `at`/`size` sind **Pflicht** = Autor-definierte Makro-Box (keine
  Auto-Ableitung aus Member-Positionen): `at` = obere linke Ecke,
  `size` = Breite/Höhe; alle 4 Werte müssen **> 0** sein
  (Validierungs-Problem `group-geometry`; R-4-Prüfung `≥ 0`/ganzzahlig
  bleibt zusätzlich wirksam). `members` = Member-Komponenten (je
  Member muss die Komponente existieren: `group-member-ref`; eine
  Komponente ist in höchstens einer Gruppe:
  `group-double-membership`; doppelte Group-IDs →
  `group-id-duplicate`). `hub` = optionale Zentralkomponente der
  Gruppe (muss ∈ `members`: `group-hub-not-member`; muss existieren:
  `group-hub-ref`); Semantik = Mikro-Layout-Verankerung (S4-L2).
  **Mikro-Layout** (Auto-Platzierung der Member innerhalb der Box)
  folgt als **R-36 (S4-L2)** — S4-L1 emittiert NUR die Makro-Box:
  gestricheltes Rect `.gbox` (kein Fill, `stroke rgba(140,160,200,0.25)`,
  `stroke-dasharray 6 4`), `id="group-<id>"`, `data-hub` (falls `hub`),
  Layer `layer-groups` **unterhalb der Zonen-Behälter** (Z-Order:
  Hintergrund → `layer-groups` → Pipes → Komponenten → Readouts →
  Labels), optionales Label `.gbox-lbl` (12 px, gedämpft
  `#8fa0bd`, oben links in der Box, Offset 8 px; nur wenn `label`
  gesetzt). Kollisions-Gate: **GROUP-BOX** (Overlap zweier Makro-Boxen
  → Kollision, exit 3; gleiche `OVERLAP_THRESHOLD`-Methodik wie die
  Text-Box-Edge-Checks: Overlap-Anteil der **kleineren** Box-Fläche
   > 50 %, eine Kollision pro Paar). GROUP-BOX×LABEL + Fremde-Box-
   Prüfung (Komponente in FREMDER Box) = R-37 (S4-L3).

- **R-36 (M, S4-L2) Mikro-Layout-Engine (intra-Gruppen-Platzierung):**
  Koordinaten werden GENERIERT, nicht gepflegt: die Autor-Pflicht ist
  die Makro-Box (`at`/`size`), die Mitglieder werden von der Engine
  (`plantschema/layout.py::resolve`) deterministisch IN die Box
  platziert. Modelländerungen: `Component.at` ist **optional**
  (Default `None`); `Group.order` (K) = explizite Mitglied-
  Reihenfolge (Default: `members`; muss Permutation von `members`
  sein: `group-order-member`); `Group.hub_at` (K) = expliziter
  Hub-Anker (Default: Box-Mitte). Pipeline-Schritt ZWISCHEN `io.load`
  und `validate` (CLI: `resolve(load_schema(…))`); danach arbeiten
  `validate`/`check`/`render` auf dem resolved Layout.
  - **Anker-Regeln:** Hub-Anker A = `hub_at` ?? Box-Mitte; hat der
    Hub ein explizites `at`, gewinnt das (Author-Override). Der Hub
    (ohne `at`) wird auf A platziert. 0 Nicht-Hub-Mitglieder → nur
    der Hub.
  - **Spalten-Split:** Nicht-Hub-Mitglieder M in `order`-Reihenfolge
    (Default: `members` minus Hub): linke Spalte = erste Hälfte
    (ceil(n/2) Slots, x = box.x + 0.28·box.w), rechte Spalte =
    Rest (x = box.x + 0.72·box.w).
  - **Zeilen:** gleichmäßig in `[box.y + 0.25·box.h,
    box.y + 0.75·box.h]` (Einzel-Element = Box-Mitte-y); je Spalte
    unabhängig voneinander.
  - **Port-Ortungs-Erhaltung (Refinement, Spalten-Zuweisung):** vor
    der Spalten-Zuweisung prüft die Engine, welche Ports des
    Mitglieds in `pipes` (from+to) genutzt werden und wo diese je
    Port-Katalog (`symbols`) liegen: nur `left`-Achsen → linke
    Spalte, nur `right`-Achsen → rechte Spalte; mehrdeutig (keine
    genutzten Ports / up-down / beides) → Spalten-Split mit
    deterministischem Tiebreak über die `order`-Reihenfolge (bei
    vollem Quoten-Topf: Überhang in die andere Spalte).
  - **Override-Hierarchie:** explizites `at` > Engine (die Engine
    überschreibt explizite `at` NIE; gilt für Hub und Mitglieder).
  - **Determinismus-Garantie:** gleiche Eingabe → gleiche
    Koordinaten; ganzzahlige Werte (`int(round(·))`, half-to-even);
    keine Randomisierung, keine zeitbasierte Heuristik.
  - **Validierung:** `component-placement-missing` (R-36) —
    `at: None` + keine bzw. nicht-eindeutige Gruppenzugehörigkeit
    (Doppel-Mitgliedschaft) → Problem (Exit 2).
  - **Gate:** `COMPONENT-OUTSIDE-GROUP-BOX` (R-36) — Mitglied,
    dessen Symbol-BBox (`SYMBOL_BOUNDS`) die **EIGENE** Makro-Box
    verlässt → Kollision (Exit 3; strikt > 0 px Überstand,
    Methode wie die bestehenden Box-Checks; Koordinaten =
    Symbol-BBox-Mitte). Fremde-Box-Prüfung = R-37.
  - **Routing-Verallgemeinerung** (Kanal-Konvention + Fremde-Box-
    Gates) folgt als **R-37 (S4-L3)**.

- **R-37 (M, S4-L3) gruppen-awarees Routing (Kanal-Konvention) +
  Fremde-Box-Gates:** Das Routing (`route.py::route_groups`, aufgerufen
  aus `emit.compute_layout`) ist gruppen-bewusst; „fremde Box" =
  Makro-Box einer Gruppe, der WEDER das from- noch das to-Ende der
  Pipe angehört (eigene Boxen beider Enden werden ausgenommen —
  eine Leitung, die in ihre Ziel-Box einläuft, ist normal).
  - **Kanal-Konvention (deterministisch):** gilt NUR ohne `via` UND
    bei inter-gruppigen Pipes (beide Enden in verschiedenen Gruppen);
    intra-gruppige Pipes (und Pipes mit nicht-gruppigem Ende) bleiben
    unverändert (via + Manhattan-Fallback). Kreuzt der orthogonale
    Fallback-Pfad das INTERIOR einer fremden Box-AABB (Kreuzungs-
    Prädikat: Orthogonal-Segment im Box-Innenband, Kanten-Tangenz
    zählt NICHT als Kreuzung), wird am **ersten** Fremdkreuzungs-
    Segment (niedrigster Segmente-Index, dann Box-Reihenfolge) ein
    eindeutiger Detour eingefügt: Die Leitung wird über die
    **nächste Kante** der Box umgeleitet (Segment-Achse: horizontales
    Kreuzungs-Segment → nächste horizontale Kante, vertikales →
    nächste vertikale Kante; Gleichstand → deterministischer Tiebreak:
    obere bzw. linke Kante). Detour-Linie = Kante ± 1 px (außen,
    „Kanal" = Linie zwischen den betroffenen Boxen, kein Kanten-Paint):
    von from-Port senkrecht auf die Kanal-Linie, entlang der Linie
    zum to-Port-Koordinatenwert, senkrecht ab zum to-Port.
  - **via-Override-Hierarchie:** `via` (Author-Route) gewinnt
    **immer** über den Detour (R-10) — auch wenn sie eine fremde Box
    kreuzt; der Router greift in via-Routen nicht ein.
  - **Determinismus-Garantie:** gleiche Eingabe → gleiche
    Punktesequenz; keine Random-/Zeit-/Hash-Heuristik, keine
    Iteration/Backtracking (KEIN allgemeines Hindernis-Vermeidungs-
    Routing). Kreuzt der Detour selbst eine weitere Box (neu), wird
    der Pfad so emittiert — das Kollisions-Gate meldet es (Exit 3)
    als erwartetes Signal, kein Crash.
  - **Gates (S4-L3):**
    - **COMPONENT-IN-FOREIGN-GROUP-BOX** (`component-in-foreign-
      group-box`, Kollision, Exit 3): Komponente, deren Symbol-BBox
      eine **fremde** Makro-Box überlappt (AABB-Overlap > 0 px,
      gleiche strikte Methodik wie COMPONENT-OUTSIDE-GROUP-BOX);
      die EIGENE Box zählt nicht (das ist R-36s Gate); signalisiert
      Fehleinsortierung; eine Kollision pro (Komponente, fremde
      Gruppe)-Paar.
    - **GROUP-BOX×LABEL** (`group-box-label`, Kollision, Exit 3):
      Label (`.txt`, `lbl-*`) überlappt eine Gruppen-Box-Kante mit
      > 50 % der Label-Text-Fläche (`OVERLAP_THRESHOLD`, gleiche
      Schwelle wie die bestehenden Box-Checks); freies Label (ohne
      Host) → alle Boxen; gebundenes Label (`comp` = Mitglied) →
      die EIGENE Gruppen-Box des Hosts wird ignoriert, alle fremden
      Boxen werden geprüft. (R-35-Ankündigung, in S4-L3 gelandet.)

- **R-38 (M, S4-L5a) Nested Groups (composite + includes + transitive
  Mitgliedschaft):** Divide-and-Conquer — eine **composite**-Gruppe
  (`kind: composite`) ist ein reiner Container: `members` leer,
  `includes` nicht leer (YAML-Referenz auf atomare Group-IDs), kein
  `hub`/`order`/`hub_at`. **Tiefe max. 1:** composite inkludiert nur
  atomare Gruppen. Eine atomare Gruppe darf von **mehreren** composites
  inkludiert werden (Venn-Kind, z. B. Puffer in Holz- und Solar-Eltern).
  `at`/`size` bleiben Pflicht (Autor-Makro-Box, keine Auto-Ableitung).
  Helfer: `plantschema/groups.py` (`transitive_members`,
  `ancestor_groups`, `membership`, `pipe_foreign_indices`).
  - **Transitive Mitgliedschaft:** `transitive_members(g)` = `members` +
    `members` aller inkludierten atomaren Gruppen (flach);
    `ancestor_groups(g)` = composites, die `g` inkludieren. Mitgliedschaft
    einer Komponente = eigene atomare Gruppe + alle composite-Ahnen.
  - **Validierung (Exit 2):** `group-kind-shape` (composite mit
    `members`/`hub`/`order`/`hub_at` oder ohne `includes`; atomic mit
    `includes`), `group-include-ref` (Include-ID existiert nicht),
    `group-include-composite` (composite inkludiert composite),
    `group-include-cycle` (Gruppe auf einem `includes`-Zyklus, defensiv).
    Hinweis: atomic mit leeren `members` bleibt (wie bisher) zulässig.
  - **Gates (Exit 3, transitive Semantik):**
    - **GROUP-CONTAINMENT** (`group-containment`, neu): jede inkludierte
      Kind-Box muss vollständig in der composite-Box liegen (keine
      Außenkante ragt heraus, Überstand > 0 px → Kollision;
      Kanten-Berührung erlaubt).
    - **GROUP-BOX** (R-35) bleibt strikt (> 50 % der kleineren Box), mit
      Ausnahmen: (a) zwei atomare Boxen mit gemeinsamem composite-
      Elternteil (Venn-Overlap), (b) zwei composite-Boxen mit ≥ 1
      gemeinsamem inkludierten Kind, (c) composite × eigenes Kind
      (Containment = GROUP-CONTAINMENT). Alle übrigen Paare (u. a.
      composite × nicht-inkludierte atomare Box) strikt wie bisher.
    - **COMPONENT-OUTSIDE-GROUP-BOX**: Komponente muss in der Box der
      eigenen atomaren Gruppe UND jedes composite-Ahnen liegen.
    - **COMPONENT-IN-FOREIGN-GROUP-BOX**: „fremd" = nicht in der
      transitiven Mitgliedschaft (eigene atomare Gruppe + Ahnen).
    - **GROUP-BOX×LABEL**: gebundenes Label ignoriert alle Boxen der
      transitiven Mitgliedschaft des Hosts; freies Label prüft alle.
  - **R-37-Refinement (Routing):** fremde Box einer inter-gruppigen
    Pipe = Box ohne transitive Mitgliedschaft der Pipe. Nicht fremd:
    atomare Gruppen beider Enden, deren composite-Ahnen und — für
    composites, die BEIDE Enden enthalten (Pipe „innerhalb" des
    composites) — alle inkludierten Kinder. Ohne gemeinsamen composite
    ist ein geteiltes Kind (bzw. ein composite ohne Bezug) fremd →
    Kanal-Detour. Ohne composites = R-37 unverändert.
  - **Emission:** composite-Boxen werden VOR den atomaren Boxen in
    `layer-groups` emittiert (liegen darunter); `<g id="group-<id>"
    data-kind="composite" data-includes="<ids>">` + `<rect class="gbox
    gbox-composite" rx="10" ry="10">` + optionales `.gbox-lbl` (oben
    links, Offset 8 px wie atomic). CSS `.gbox-composite`
    (`stroke-width:2`, `stroke-dasharray:10 5`, kräftigere Farbe) wird
    NUR emittiert, wenn das Schema composites enthält → Schemas ohne
    composites bleiben byte-identisch (Hash-Stabilität).
  - **`frame` (S4-L5c, Default-Regel):** Rahmen (`<rect>`) + Label
    (`.gbox-lbl`) werden gezeichnet **gdw.** `frame: true` ODER
    (`frame` fehlt UND `kind: atomic`). composite ohne `frame` → kein
    Rahmen, kein Label (nur der leere Wrapper `<g id="group-<id>"
    data-kind="composite" data-includes=…>` bleibt als ID-Vertrag).
    `frame: false` unterdrückt immer Rahmen UND Label. CSS
    `.gbox-composite` nur, wenn mind. ein composite gerahmt ist. Reine
    Darstellung: **alle Gates** (GROUP-BOX, GROUP-CONTAINMENT,
    COMPONENT-*, GROUP-BOX×LABEL) und das Routing arbeiten unverändert
    auf `at`/`size`.

## 4c. Lane (S4-L5b, R-39)

| Feld | Typ | Pflicht |
|---|---|---|
| `id` | string (R-3; eindeutig über alle Arten, R-5) | M |
| `label` | string (Box-Beschriftung) | K |
| `at` | `[x, y]` obere linke Ecke der Lane-Box (> 0) | M |
| `size` | `[w, h]` Breite/Höhe (> 0) | M |
| `pipes` | list[string] (Pipe-IDs, R-3; nicht leer) | M |
| `frame` (S4-L5c, R-39) | bool; Default `None` = **an** | K |

- **R-39 (M, S4-L5b) Lanes = Leitungs-Reservierung:** Eine Lane ist
  KEINE Gruppe (kein `members`/`hub`/`kind`), sondern ein reservierter
  Routing-Korridor (Modul `plantschema/lanes.py`). Eine Pipe steht in
  höchstens einer Lane; `Pipe` selbst hat keine neuen Felder.
  - **Geometrie:** Achse = längere Box-Seite (`w >= h` → horizontal,
    sonst vertikal). Spur der i-ten Pipe (0-basiert, Reihenfolge =
    `lane.pipes`): horizontal `y_i = y + h/2 − (n−1)/2·S + i·S`,
    vertikal analog `x_i` (zentriert, gleichmäßig; `S` =
    `lanes.LANE_SPACING` = 10 px; ganzzahlig gerundet).
  - **Enge Box:** `(n−1)/2·S > (Quer-Ausdehnung)/2` → `S` halbiert
    (5 px, deterministisch) + Warnung `LANE-FALLBACK` (R-33-Stil,
    Exit bleibt 0).
  - **Auto-Route** (Pipe in `lane.pipes`, OHNE `via`): orthogonal über
    die Spur — horizontal `from → (from.x, y_i) → (to.x, y_i) → to`,
    vertikal `from → (x_i, from.y) → (x_i, to.y) → to`; kein
    R-37-Detour. **`via` gewinnt immer** (R-37-Override).
  - **Degeneriert:** beide Ports auf derselben Koordinate entlang der
    Lane-Achse (horizontal: gleiches x, vertikal: gleiches y) → kein
    Lauf entlang der Lane → R-37/Manhattan-Fallback. Berührt die
    Fallback-Route die Box → ok; sonst Warnung `LANE-FALLBACK @
    pipe-<id>` statt LANE-PIPE-Treffer.
  - Nicht-Lane-Pipes: R-37 unverändert.
  - **Validierung (Exit 2):** `lane-id-duplicate`, `lane-geometry`
    (`at`/`size` fehlen oder ≤ 0), `lane-pipe-ref`,
    `lane-pipe-duplicate` (Pipe in > 1 Lane bzw. doppelt in einer).
  - **Gates (Exit 3):** **LANE-BOX** (`lane-box`: zwei Lane-Boxen
    überlappen > 50 % der kleineren Fläche, Methodik wie GROUP-BOX) +
    **LANE-PIPE** (`lane-pipe`: Pipe in `lane.pipes` ohne Segment in
    der Lane-Box; Kanten-Berührung ≤ 2 px zählt als innerhalb;
    degenerierte Pipes ohne `via` ausgenommen). Lane-Boxen sind keine
    Gruppen-Boxen (kein Einfluss auf COMPONENT-OUTSIDE/-FOREIGN,
    GROUP-BOX, GROUP-BOX×LABEL); Komponenten dürfen in Lane-Boxen liegen.
  - **Emission:** `layer-lanes` (nach `layer-groups`, vor
    `layer-pipes`) — NUR wenn Lanes existieren; `<g id="lane-<id>"
    data-axis="horizontal|vertical" data-pipes="<ids>">` + `<rect
    class="lane">` + optionales `.lane-lbl` (oben links, Offset 6/12 px).
    CSS `.lane` (gestrichelt `3 3`, `stroke rgba(200,180,140,0.30)`) /
    `.lane-lbl` (10 px) nur bei vorhandenen Lanes → Schemas ohne Lanes
    bleiben byte-identisch.
  - **`frame` (S4-L5c, Default-Regel):** Rahmen + Label gdw. `frame`
    fehlt ODER `frame: true`; `frame: false` → nur der leere Wrapper
    `<g id="lane-<id>" data-axis data-pipes>`. Spuren, Routing,
    LANE-BOX/LANE-PIPE unverändert (arbeiten auf `at`/`size`).

## 4d. hidden_kinds (S4-L5c, R-41)

- **R-41 (M, S4-L5c) `hidden_kinds` = SVG-Display-Option:** Top-Level
  `hidden_kinds: list[vl|rl|ww|gas|ctl]` (Default `[]`; unbekannter
  Kind → Schema-Fehler, Exit 2). Das Modell bleibt vollständig
  (Pipes werden geladen, validiert, geroutet). Wirkung NUR auf:
  - **Emission:** Pipes mit `kind ∈ hidden_kinds` werden nicht
    gezeichnet (weder `pipe-<id>` noch `.pipe-arrow`).
  - **Slots (R-32/R-33):** ausgeblendete Pipes blockieren keine
    Label-Slots (keine SLOT-FALLBACK-Warnung durch sie).
  - **Gate (R-34):** ausgeblendete Pipes sind kein Hindernis
    (LINE×TEXT; LANE-PIPE). `check` kann dadurch Exit 0 liefern.
  - **Stutzen (R-42):** zählen nicht als Verbindung.
  - **Validierung:** `hidden-pipe-in-lane` (Exit 2) — eine Pipe mit
    ausgeblendetem Kind darf in keiner `lane.pipes` stehen.
  - **Determinismus:** `hidden_kinds: []` (bzw. nur Kinds ohne Pipes)
    → byte-identisch zum Stand ohne das Feld.

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

- **R-40 (M, S4-L5b) Junction (Knoten-Symbol):** Komponententyp
  `junction` = sichtbare Verschaltung/Verteiler (normale Komponente:
  `id`, `type: junction`, optional `at`/`label`; darf in Gruppen und
  Lane-Boxen liegen). Symbol `pid-junction` (Erweiterung, NICHT aus dem
  cmi-Seed): gefüllter Kreis Radius 6 (`<circle class="pid" r="3"
  style="stroke-width:6"/>` — Standard-`.pid`-Stil, kein Fill-Farb-
  Change). Ports `left`/`right`/`top`/`bottom` (Kanten-Mitte, ±6),
  BBox (−6, −6, +6, +6), Label-Offset 18. `pid-junction` steht im
  `<defs>` NUR, wenn das Schema eine junction enthält (Byte-Stabilität
  der 18-Symbol-Defs).

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
| `junction` (S4-L5b, R-40) | `left` (−6,0, left) · `right` (+6,0, right) · `top` (0,−6, up) · `bottom` (0,+6, down) |

- **R-31 (S, S2) Typ→Symbol-Mapping:** 1:1 (`tank-buffer` →
  `pid-tank-buffer` …, `pump` → `pid-pump-cent`); Alias `valve` =
  2-Wege-Default (`pid-valve-2way` + valve-2way-Geometrie).
  **Label-Offset (S3, R-32):** `.txt-h`/`.txt-s` stehen im **up-Slot**
  (8 px über der Symbol-Oberkante; 2 Zeilen mit Sub: Haupt-Baseline
  20 px, Sub 17 px darunter — Sub-Unterkante exakt an der Kante),
  `place.component_label_offset`; alle-4-Slots-kollidieren → Fallback
  + Warning (R-33). (S2-Katalog `symbols.LABEL_OFFSET` bleibt als
  Referenz-/Fallback-Katalog.)

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
| `at` | `[x, y]` (R-4) | K (S3: exklusiv zu `comp`) |
| `comp` | string (R-3) | K (S3: Host-Komponente) |
| `port` | string (klein) | K (S3: Port am Host, optional) |
| `text` | string | M |
| `anchor` | `start\|middle\|end` (default `start`) | K |

- **R-16 (M)** Position im Canvas (x ≤ width, y ≤ height): `at`-Labels
  exakt; Auto-Slot-Labels die aufgelöste Slot-Position.
- **R-17 (S3) Label-Placement (R-32):** Entweder `at` **oder** `comp`
  (+ optional `port`) — nicht beides, nicht keines (sonst
  `label-placement`, R-32). `at` = exakte Position (**Override, gewinnt
  immer**); `comp` = Auto-Slot um den Host (s. R-32).
- **R-32 (M, S3) Slot-Präferenz + Mindestabstand:** Auto-Slot-Reihenfolge
  **up → right → down → left** (Kanon); Slot-Text-Position an der
  Symbol-Kante (`symbols.SYMBOL_BOUNDS`): up/down = 8 px über/unter
  (anchor=middle), left/right = 16 px links/rechts (anchor end/start,
  Readout-`side`-Kanon). Erster Slot mit **≥ 8 px** zu allen
  Pipe-Segmenten (5-px-Sampling) + ≥ 8 px zu allen anderen
  Symbol-Bounding-Boxes + **≥ 4 px** zu allen anderen Text-BBs wird
  genommen. `port` verschiebt den Slot entlang der Slot-Kante (Port-
  Offset, begrenzt auf Kante ± 0.5·Textgröße) und erzwingt die Richtung
  des Port-Offsets (Präferenzkette startet dort).
  *Präzisierung (S4-L4):* „Pipe-Segmente" = die **emittierte** Route
  (`route.schema_routes` ≡ `emit.compute_layout`: via-Override +
  R-37-Kanal-Detour), nicht der reine Manhattan-Fallback — Slot-
  Evaluation, Emission und Gate prüfen dieselbe Geometrie.
- **R-33 (M, S3) Slot-Fallback:** Alle 4 Slots kollidieren → Position =
  **up-Slot** + **Warning** (kein Gate-Fehler; Report-Block
  „N Warnung(en):" vor den Kollisionen, Exit bleibt 0). Gilt auch für
  Komponenten-Labels (`.txt-h`/`.txt-s`).

## 8. Canvas

- **R-18 (M)** `width`/`height` > 100 (sonst `canvas-too-small`).
- **R-19 (S)** `background` = hex-Farbe (default `#0b1220`); emittiert als
  `<rect id="canvas-bg">` unterste Ebene.

## 9. Validierung (S1/S3-Problem-Codes)

| Code | Prüfung |
|---|---|
| `dup-id` | ID mehr als einmal (alle Arten, R-5) |
| `ref-component` | Pipe/Readout zeigt auf fehlende Komponente (R-8, R-13) |
| `ref-port` | Pipe/Readout-Port nicht im (Override-geprägten) Port-Set (R-9, R-13) |
| `label-comp-ref` | Label.comp zeigt auf fehlende Komponente (R-32, S3) |
| `label-port-ref` | Label.port nicht im Port-Set des Hosts (R-32, S3) |
| `label-placement` | Label weder `at` noch `comp` (R-32, S3) |
| `out-of-canvas` | Readout/Label außerhalb des Canvas (R-14, R-16) |
| `canvas-too-small` | width/height ≤ 100 (R-18) |
| `unknown-type` | Komponententyp nicht im Katalog (R-6) |
| `group-id-duplicate` | doppelte Group-ID (Group×Group, R-35; Group×fremde-Art bleibt `dup-id`, R-5) |
| `group-member-ref` | Group-Member existiert nicht als Komponente (R-35) |
| `group-hub-ref` | Group-Hub existiert nicht als Komponente (R-35) |
| `group-hub-not-member` | Group-Hub ∉ members (R-35) |
| `group-double-membership` | Komponente in > 1 Gruppe (R-35) |
| `group-geometry` | `at`/`size` mit Wert ≤ 0 (R-35, Makro-Box-Kanon) |
| `group-order-member` | `order` ist keine Permutation von `members` (R-36, S4-L2) |
| `component-placement-missing` | `at: None` + keine/nicht-eindeutige Gruppenzugehörigkeit (R-36, S4-L2) |
| `component-in-foreign-group-box` | **Kollisions-Gate-Code** (nicht validate; S4-L3, R-37, Exit 3): Komponente in fremder Gruppen-Box (Overlap > 0 px, eigene Box ausgenommen) — s. R-37/§12 |
| `group-box-label` | **Kollisions-Gate-Code** (nicht validate; S4-L3, R-37, Exit 3): Label > 50 % der Text-Fläche in fremder Gruppen-Box (gebundene Labels: eigene Box ausgenommen) — s. R-37/§12 |
| `group-kind-shape` | composite mit `members`/`hub`/`order`/`hub_at` oder ohne `includes`; atomic mit `includes` (R-38, S4-L5a) |
| `group-include-ref` | `includes`-ID existiert nicht als Gruppe (R-38, S4-L5a) |
| `group-include-composite` | composite inkludiert composite (Tiefe max. 1, R-38, S4-L5a) |
| `group-include-cycle` | Gruppe liegt auf einem `includes`-Zyklus (defensiv, R-38, S4-L5a) |
| `group-containment` | **Kollisions-Gate-Code** (nicht validate; S4-L5a, R-38, Exit 3): inkludierte Kind-Box ragt aus der composite-Box heraus — s. R-38/§12 |
| `lane-id-duplicate` | doppelte Lane-ID (Lane×Lane, R-39; Lane×fremde-Art bleibt `dup-id`, R-5) |
| `lane-geometry` | Lane-`at`/`size` fehlt oder Wert ≤ 0 (R-39) |
| `lane-pipe-ref` | Pipe-ID in `lane.pipes` existiert nicht (R-39) |
| `lane-pipe-duplicate` | Pipe steht in > 1 Lane (bzw. doppelt in einer Lane, R-39) |
| `hidden-pipe-in-lane` | Pipe mit `kind ∈ hidden_kinds` steht in einer `lane.pipes` (S4-L5c, R-41) |
| `lane-box` | **Kollisions-Gate-Code** (nicht validate; S4-L5b, R-39, Exit 3): zwei Lane-Boxen überlappen > 50 % der kleineren Box |
| `lane-pipe` | **Kollisions-Gate-Code** (nicht validate; S4-L5b, R-39, Exit 3): Lane-Pipe ohne Segment in der Lane-Box (≤ 2 px Berührung = innen) |

- **R-20 (M)** `validate` liefert **alle** Probleme (nicht nur das erste);
  CLI gibt je Problem eine Zeile aus und exitet 2.

## 10. SVG-Vertrag (stabile IDs + data-Attribute)

| Element | ID / Attribut | Bedeutung |
|---|---|---|
| `<defs>` | `#arrow` + `#pid-…` (18 Symbole) | P&ID-Katalog (S2, byte-identisch cmi-Seed); Symbol-IDs sind Referenz-Ziele, keine Artefakt-Elemente |
| Komponente | `g[@id="comp-<id>"]` | + `data-type`, `data-loop` (falls gesetzt), `data-flow` (falls `flow`), `data-symbol="pid-…"` (bekannt) bzw. `data-symbol="placeholder"` (S1-Fallback); Inhalt: `<use href="#pid-…">` (x/y = at) + Label-Texte `.txt-h`/`.txt-s` oben (R-31) |
| Pipe | `path[@id="pipe-<id>"]` | + `data-kind`, `data-flow` (falls `flow`), `class="pipe <kind>"`; **kein** `marker-end` (S2, R-29) |
| Pfeil-Endpunkt | `path[@class="pipe-arrow arrow-<kind>"]` | Kleines Dreieck am Pipe-Ende (S2, R-29), Fill = Kind-Farbe |
| Gruppe-Box | `g[@id="group-<id>"]` in `layer-groups` | + `data-hub` (falls `hub`); Inhalt: `<rect class="gbox">` (x/y = `at`, width/height = `size`) + optionales Label-Text `.gbox-lbl` (oben links, Offset 8 px; S4-L1, R-35) |
| composite-Box (S4-L5a, R-38) | `g[@id="group-<id>"]` in `layer-groups` (vor den atomaren Boxen) | + `data-kind="composite"`, `data-includes` (Leerzeichen-getrennte Kind-IDs); Inhalt: `<rect class="gbox gbox-composite" rx="10" ry="10">` + optionales `.gbox-lbl`; CSS `.gbox-composite` nur bei vorhandenen composites |
| Lane-Box (S4-L5b, R-39) | `g[@id="lane-<id>"]` in `layer-lanes` | + `data-axis` (`horizontal`/`vertical`), `data-pipes` (Leerzeichen-getrennte Pipe-IDs); Inhalt: `<rect class="lane">` + optionales `.lane-lbl` (oben links, Offset 6/12 px); CSS `.lane`/`.lane-lbl` nur bei vorhandenen Lanes |
| junction (S4-L5b, R-40) | `g[@id="comp-<id>"]` | wie jede Komponente (`data-type="junction"`, `data-symbol="pid-junction"`, `<use href="#pid-junction">`); `#pid-junction` im `<defs>` nur bei vorhandener junction |
| Stutzen (S4-L5c, R-42) | `path[@class="stub <kind>"]` in `layer-components`, direkt nach `comp-<id>` | + `data-comp`, `data-port`; Gerade BBox-Kante → Port; CSS `.stub` nur bei vorhandenen Stutzen |
| Readout | `g[@id="readout-<id>"]` | + `data-value-key` (falls gesetzt), `data-readout` = Label-Text, `data-loop` (falls gesetzt); Inhalt: `<use href="#pid-pt">` + Wert `.ro-val` (`data-value="true"`) + Label `.ro-lbl` (cmi-Kanon; `side` → `text-anchor`, R-15) |
| Label | `text[@id="lbl-<id>"]` | + `text-anchor`, `class="txt"` |
| Layer | `layer-groups`, (`layer-lanes`), `layer-pipes`, `layer-components`, `layer-readouts`, `layer-labels` | Reihenfolge = Z-Order (R-2; `layer-groups` = S4-L1, R-35, unterhalb der Zonen-Behälter; `layer-lanes` = S4-L5b, R-39, nur bei vorhandenen Lanes) |

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

## 12. Kollisions-Gate (S1/S3)

- **R-26 (M)** Gate-Prüfungen S1: **TEXT×TEXT** (Bounding-Box-
  Intersektion, cmi-Heuristik: width ≈ font_size·0.52·len, Höhe ≈
  font_size·1.2) + **LINE×TEXT** (Pipe-Segment läuft durch Text-BBox,
  Sampling 5 px, ≥ 2 Treffer). S3-Check-Set: s. R-34.
  S3-Input: Readout-Texte = `.ro-val` (12 px) + `.ro-lbl` (11 px) mit
  Emissions-Position/Anker (`side`); Labels = `.txt` (Auto-Slot-Position
  laut R-32); Komponenten-Labels = `.txt-h`/`.txt-s` (up-Slot, R-31/R-32).
- **R-27 (M)** Kollision → exit 3 + Report (R-34-Format); `--no-gate` =
  Debug-Aus.
- **R-28 (S→M, S3)** Readout-/Label-Größen: Wert ≥ 12 px, Label ≥
  11 px (`place.VALUE_FONT_MIN`/`LABEL_FONT_MIN`; Emissions-Klassen
  `.ro-val`/`.ro-lbl` = 12/11 px → Gate-Prüfung `readout-size`, R-34).
- **R-34 (M, S3) Kollisions-Check-Set + Report-Format (cmi
  `svg_layout_check.py`-Kanon, `OVERLAP_THRESHOLD`-Schwelle):**
  1. **TEXT×TEXT** (`text-text`): zwei Text-BBs überlappen (S1,
     2-px-Nachte + echte Überdeckung).
  2. **LINE×TEXT** (`line-text`): Pipe-Segment läuft durch Text-BBox
     (5-px-Sampling, ≥ 2 Treffer; S1 unverändert).
  3. **TEXT×BOX-Kante** (`text-box-edge`) + **USE×TEXT**
     (`symbol-text`): Text-BBox × Symbol-Bounding-Box
     (`symbols.SYMBOL_BOUNDS`, R-34-Katalog) → Kollision **nur wenn der
     Overlap-Anteil > 50 % der Text-Fläche** liegt (cmi `overlap_area`-
     Logik, Konstante `OVERLAP_THRESHOLD=0.5`); darunter = „Text neben
     Symbol" erlaubt. Labels (`.txt`, `lbl-*`) → `text-box-edge`,
     Readout-/Komponenten-Texte → `symbol-text`. **Eine Kollision pro
     (Text, Symbol)-Paar** (dedupliziert).
  4. **Readout-Größen-Gate** (`readout-size`): emittierter Readout-Text
     Wert ≥ 12 px, Label ≥ 11 px (R-28, harte Prüfung).
  5. **GROUP-BOX** (`group-box`, R-35/S4-L1): Overlap zweier Makro-
     Boxen (Kanon s. R-35). 6. **COMPONENT-OUTSIDE-GROUP-BOX**
     (`component-outside-group-box`, R-36/S4-L2): Mitglied außerhalb
     der EIGENEN Makro-Box (Kanon s. R-36).
   7. **COMPONENT-IN-FOREIGN-GROUP-BOX** (`component-in-foreign-
      group-box`, R-37/S4-L3): Komponente in FREMDER Makro-Box
      (Overlap > 0 px; Kanon s. R-37). 8. **GROUP-BOX×LABEL**
      (`group-box-label`, R-37/S4-L3): Label > 50 % Text-Fläche in
      fremder Makro-Box (gebundene Labels ignorieren die eigene
      Box; Kanon s. R-37).
   9. **GROUP-CONTAINMENT** (`group-containment`, R-38/S4-L5a):
      Kind-Box ragt aus composite-Box heraus (> 0 px). Gates 5–8
      nutzen ab S4-L5a die transitive Mitgliedschaft (Kanon s. R-38).
  10. **LANE-BOX** (`lane-box`, R-39/S4-L5b): zwei Lane-Boxen > 50 %
      der kleineren Fläche. 11. **LANE-PIPE** (`lane-pipe`,
      R-39/S4-L5b): Lane-Pipe ohne Segment in der Lane-Box (Kanon s.
      R-39). Warnungs-Block enthält zusätzlich `LANE-FALLBACK`-Zeilen
      (enge Lane / degenerierte Pipe ohne Box-Berührung; Exit bleibt 0).
  Kanon-BBox: `text-anchor`-Korrektur (`end` → x = anchor_x − width,
  `middle` → x = anchor_x − width/2; cmi `text_bbox`-Logik).
  **Report-Format:** je Kollision eine Zeile
  `KIND  [elemA] × [elemB] @ (x,y) — Hinweis` + am Ende
  `N Kollision(en):` (Summe); vor den Kollisionen optional der
  Warnungs-Block `N Warnung(en):` (R-33-Slot-Fallbacks, **Exit bleibt
  0** — Warnungen ≠ Fehler); bei 0 Kollisionen: Exit 0 (kein
  Kollisions-Block).

### SYMBOL_BOUNDS-Katalog (S3, R-34: Bounding-Box je Komponententyp)

`plantschema.SYMBOL_BOUNDS`: lokale BBox (x0, y0, x1, y1) um (0,0),
**abgeleitet aus der cmi-Symbol-Geometrie** (`ui/svg/pid-symbols.svg`-
Seed: Umschließung aller gezeichneten Elemente — Rechtecke, Kreise,
Stiele, Pfeil-Enden; `valve`-Alias = valve-2way):

| Typ | BBox (x0, y0, x1, y1) | Typ | BBox (x0, y0, x1, y1) |
|---|---|---|---|
| `tank-buffer` | (−30, −60, +30, +60) | `valve-2way` | (−20, −21, +20, +10) |
| `boiler-oil` | (−28, −44, +28, +29) | `valve-3way` | (−20, −9, +20, +20) |
| `boiler-solid` | (−28, −48, +28, +36) | `valve-globe` | (−20, −22, +20, +10) |
| `collector-solar` | (−41, −14, +41, +14) | `valve-actuator` | (−20, −35, +20, +10) |
| `heatex-plate` | (−35, −15, +35, +18) | `throttle` | (−20, −30, +20, +10) |
| `heatex-shell` | (−30, −11, +30, +20) | `radiator` | (−30, −13, +30, +13) |
| `mixing` | (−14, −11, +14, +14) | `tap` | (−14, −7, +14, +23) |
| `pump` | (−20, −13, +20, +22) | `chimney` | (−14, −40, +18, +34) |
| `pt`, `flow-switch` | (−8, −8, +8, +16) | Platzhalter (unbekannter Typ) | (−20, −20, +20, +20) |
| `junction` (R-40) | (−6, −6, +6, +6) | | |

- **R-42 (M, S4-L5c) Stutzen / Docking-Connector:** Leitungen docken
  außerhalb des Symbols an. Für jeden Port, der **strikt im Inneren**
  der `SYMBOL_BOUNDS`-BBox liegt (`x0 < dx < x1` und `y0 < dy < y1`)
  UND an dem mind. eine sichtbare Pipe (`from`/`to`, Kind ∉
  `hidden_kinds`) endet, wird ein Stutzen gezeichnet: Gerade vom
  BBox-Kantenpunkt auf der Port-Achse (up/down: `(dx, y0|y1)`,
  left/right: `(x0|x1, dy)`) zum Port. Katalog (`symbols.port_stubs`,
  Alias-aware): tank-buffer mid-top/mid-bottom, boiler-oil top/bottom,
  boiler-solid top/bottom, heatex-plate top/bottom, chimney left/right,
  valve-2way/valve/valve-globe/valve-actuator/throttle stem, tap draw.
  Keine Stutzen: junction (Ports auf der Kante), flow-switch/pt (keine
  Ports), mixing (`top` (0,−14) liegt über y0 = −11, nicht innen).
  Farbe = Kind der ersten verbundenen Pipe (Schema-Reihenfolge,
  `class="stub <kind>"`), `.stub{stroke-width:3}`. Pipe-Geometrie,
  Routing, Slots und Gates bleiben unverändert (Endpunkte am Port).

- **ALC-Änderung (S3):** `Label.at` optional + neue Felder
  `Label.comp`/`Label.port` (Auto-Slots, R-32/R-33); neue
  Validierungs-Probleme `label-comp-ref`/`label-port-ref`/
  `label-placement`; Komponenten-Labels stehen im up-Slot statt
  `LABEL_OFFSET` (S2); Gate-Report: Warnungs-Block (R-33) vor den
  Kollisionen; neue Check-Arten `text-box-edge`/`symbol-text`/
  `readout-size` (R-34); `SYMBOL_BOUNDS`-Katalog (R-34).

- **ALC-Änderung (S4-L1):** neue Root-Liste `groups` (default `[]`) +
  `Group`-Modell (R-35, Makro-Geometrie `at`/`size` = Autor-Pflicht);
  Emission: `layer-groups` (neu, Z-Order vor `layer-pipes`) +
  `.gbox`/`.gbox-lbl`-Style-Klassen + `group-*`-ID-Präfix; neues
  Gate-Check `group-box` (R-35-Overlap); 6 neue Validierungs-Probleme
  (`group-id-duplicate`, `group-member-ref`, `group-hub-ref`,
  `group-hub-not-member`, `group-double-membership`,
  `group-geometry`); bestehende R-1…R-34 unverändert.

- **ALC-Änderung (S4-L2):** `Component.at` optional (Default `None`,
  R-36: Engine-Placement für Gruppen-Mitglieder); `Group.order` +
  `Group.hub_at` neu (K); Mikro-Layout-Engine `layout.resolve`
  (Pipeline-Schritt zwischen load und validate, R-36); 2 neue
  Validierungs-Probleme (`component-placement-missing`,
  `group-order-member`); neues Gate-Check `component-outside-group-box`
  (R-36); bestehende R-1…R-35 unverändert.

- **ALC-Änderung (S4-L5b):** neue Root-Liste `lanes` (default `[]`) +
  `Lane`-Modell (R-39); neuer Komponententyp `junction` (R-40); Modul
  `lanes.py` (`LANE_SPACING`, Spuren, Zuordnung, Warnungen); Routing
  `route.route_lane` (Lane-Auto-Route, via-Override, degenerierter
  R-37-Fallback); 4 neue Validierungs-Probleme (`lane-id-duplicate`,
  `lane-geometry`, `lane-pipe-ref`, `lane-pipe-duplicate`); 2 neue
  Gate-Checks (`lane-box`, `lane-pipe`); Warnung `LANE-FALLBACK`;
  Emission `layer-lanes`/`.lane`/`.lane-lbl` und `#pid-junction` nur
  bei Bedarf (Schemas ohne Lanes/junctions byte-identisch);
  bestehende R-1…R-38 unverändert.

- **ALC-Änderung (S4-L5c):** `Group.frame`/`Lane.frame` (K; composite-
  Default **ohne** Rahmen+Label → geänderte SVGs aller composite-
  Schemas); Root-Feld `hidden_kinds` (R-41) + Validierungs-Problem
  `hidden-pipe-in-lane`; `detect_collisions(..., hidden_kinds=)`;
  Stutzen `.stub` (R-42) → geänderte SVGs aller Schemas mit
  verbundenen Innen-Ports. Schemas ohne composites und ohne solche
  Ports bleiben byte-identisch; Gates/Routing unverändert.

## 13. Exit-Codes (CLI-Kanon)

| Exit | Bedeutung |
|---|---|
| 0 | ok |
| 2 | Schema-/Validierungsfehler (Stderr: `[line N] path: message`) |
| 3 | Gate-Fehler (Kollisionen, je Kollision eine Zeile) |
| 4 | IO-Fehler (Datei fehlt, unlesbar, ungültiges YAML) |
