<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/logo-dark.svg?v=2">
    <img alt="episteme" src="docs/assets/logo-light.svg?v=2" width="456">
  </picture>
</h1>

<p align="center">
  <a href="https://github.com/junjslee/episteme/releases"><img alt="Latest Release" src="https://img.shields.io/github/v/release/junjslee/episteme?include_prereleases&label=release&logo=github"></a>
  <a href="https://github.com/junjslee/episteme/blob/master/LICENSE"><img alt="License" src="https://img.shields.io/github/license/junjslee/episteme?color=informational"></a>
  <a href="https://github.com/junjslee/episteme"><img alt="Unique Clones" src="https://img.shields.io/badge/dynamic/json?color=success&label=Unique%20Clones&query=uniques&url=https://gist.githubusercontent.com/junjslee/0a171c9a54b11948bbd1562f4f040465/raw/clone.json&logo=github"></a>
</p>

<p align="center">
  <a href="README.md">English</a> &bull;
  <a href="README.ko.md">한국어</a> &bull;
  <a href="README.es.md"><b>Español</b></a> &bull;
  <a href="README.zh.md">中文</a>
</p>

<p align="center"><a href="https://epistemekernel.com"><b>epistemekernel.com</b></a></p>

> **episteme es una forma de pensar — 생각의 틀 — un motor epistémico (epistemic engine) que obliga a las decisiones asistidas por IA a ganarse su confianza antes de ejecutarse.**
>
> Una práctica cognitiva de cinco etapas — **Frame (encuadrar) → Decompose (descomponer) → Execute (ejecutar) → Verify (verificar) → Handoff (entregar)** — anclada en el forzado del System-2 de Kahneman, la Radical Transparency de Dalio, la OODA Orientation de Boyd y el Latticework of Mental Models de Munger. La v2.0 la entrega en tres capas. **Cognición** — la interrogación del investigador senior: descomponer una decisión de carga en afirmaciones clasificadas (`measured / cited / inferred / assumed`), verificar las afirmaciones de carga *en un contexto fresco contra evidencia externa* (el verificador nunca ve el borrador), argumentar la oposición más fuerte, nombrar el eslabón más débil, comprometer por adelantado una condición de refutación. **Estructura** — hooks deterministas que enrutan las formas de decisión, validan el artefacto de veredicto (un veredicto `stop` falla cerrado) y bloquean duro solo las operaciones genuinamente destructivas; la Reasoning Surface firmada por el operador (Ed25519, estructuralmente fuera del alcance del agente) sigue siendo el artefacto de encuadre del lado del operador. **Memoria** — las lecciones de interrogaciones verificadas se vuelven protocolos encadenados por hash y acotados por contexto, que reaparecen en la siguiente decisión coincidente. La división del trabajo la fijó el registro de investigación, no nosotros: los modelos que juzgan sus propios borradores *empeoran*, los chequeos de forma se burlan con tokens con forma de razonamiento, y solo la restricción arquitectónica convierte la conciencia epistémica en conducta.
>
> El benchmark MIRROR ([arXiv 2604.19809](https://arxiv.org/abs/2604.19809)) zanjó la cuestión empírica: en 16 modelos de 8 laboratorios y ~250.000 instancias, *"proporcionar a los modelos sus propias puntuaciones de calibración no produce ninguna mejora significativa; solo la restricción arquitectónica es efectiva."* La Confident Failure Rate cae de 0,60 a 0,14 bajo restricción arquitectónica externa. **La práctica misma es el producto.** Los artefactos bajo `core/` y `src/episteme/` son geometría de imposición (enforcement geometry) que permite que la práctica sobreviva cuando la *vigilancia como fuerza de voluntad* se derrumba a la potencia de los modelos de frontera.
>
> **→ [`docs/THE_WAY_TO_THINK.md`](docs/THE_WAY_TO_THINK.md)** — la práctica operacionalizada.

---

## Por qué los prompts no son la verdad

Le pides al agente: *"Evalúa si nuestro sistema de memoria con retrieval-augmented (RAG) está realmente mejorando la calidad de las respuestas."*

El agente trata tu prompt como una tarea de medición. Saca métricas de los últimos 30 días, compara muestras de respuestas con-memoria vs sin-memoria, encuentra un 7% de lift positivo en la tasa de thumbs-up, escribe un memo concluyendo "la memoria ayuda; sigamos enviando." Lo lees.

El agente no hizo las preguntas que tú habrías hecho, si no estuvieras cansado:

- **Qué (What)** está midiendo realmente la "calidad" aquí? La métrica que el agente eligió fue la *tasa de thumbs-up*. Pero el thumbs-up correlaciona con la *confianza* de la respuesta, no con su *corrección* — una respuesta confiadamente equivocada con cita de memoria puede puntuar mejor que una respuesta correctamente incierta sin ella. El agente midió un proxy de la pregunta, no la pregunta.
- **Por qué (Why)** ayudaría la memoria? El mecanismo propuesto es contexto estable entre sesiones. Pero la comparación con/sin no controló la longitud de respuesta — las respuestas con memoria son un 30% más largas en promedio, y la longitud por sí misma correlaciona con thumbs-up. El "lift" podría ser efecto de longitud, no de memoria.
- **Cómo (How)** sería errónea esta conclusión? Re-corre el experimento controlando longitud de respuesta. Si el lift persiste, la memoria está haciendo trabajo real. Si desaparece, la memoria añade tokens pero no señal. Esa es la condición de refutación que el agente nunca nombró.

Un agente naïve da una respuesta que suena medida porque el prompt pidió una medición. `episteme` obliga al agente a escribir — en disco, antes de que el memo se entregue — qué mide realmente la medición, qué mecanismo se está reclamando, y qué resultado observable refutaría la afirmación. El acto de escribirlo expone que el proxy no era la pregunta.

Trabajo académico reciente llama a la brecha acumulada entre lo que el agente sabe en contexto, lo que tú pretendes, y lo que tu sistema realmente requiere **Epistemic Drift**. `episteme` cierra esa brecha exigiendo estructuralmente al agente que razone — *qué · por qué · cómo* — antes de actuar.

---

## Por qué los prompts no son suficientes

- Un recordatorio en el system prompt **vive solo una llamada**.
- Una nota en `CLAUDE.md` **se ignora cuando llega el deadline** — tanto los humanos como los agentes lo hacen.
- **El know-how** — la regla irreduciblemente específica al contexto de *"en esta forma de problema, haz esto"* — no se enseña con mejor redacción. Tiene que ser **extraído, almacenado y re-emergido**.

Y lo más profundo: el agente **ejecuta incluso cuando la solicitud del usuario es incorrecta**. Los usuarios también pueden carecer de profundidad, malinterpretar o partir de premisas erróneas. Un buen sistema *no solo vigila al agente, también valida la pregunta misma del usuario*. Los parches a nivel de prompt no estructuran esta validación bidireccional.

---

## La solución — un Thinking Framework a nivel del sistema de archivos

`episteme` intercepta **el momento en que la intención se encuentra con el cambio de estado**. Antes de cualquier operación de alto impacto (`git push`, `npm publish`, `terraform apply`, migraciones de DB, edición de lockfiles) — sin importar *quién* la solicitó (el usuario o el propio agente) — el agente debe proyectar su razonamiento explícitamente en una **Reasoning Surface** de cuatro campos en el disco:

| Campo | Qué debe declarar el agente |
|---|---|
| **Core Question** | La única pregunta que esta acción realmente intenta responder (contra la question substitution) |
| **Knowns** | Hechos verificados, citas, mediciones — no suposiciones que suenan bien |
| **Unknowns** | Vacíos nombrados y clasificables — no un vago *"puede haber riesgos"* |
| **Assumptions** | Creencias que soportan la carga, marcadas para que puedan ser falsificadas |
| **Disconfirmation** | El evento observable que *probaría que este plan está mal* — comprometido antes de actuar |

La validación es **estructural**: longitud mínima, prohibición de placeholders perezosos (`none`, `n/a`, `tbd`, `해당 없음`), escaneo normalizado de comandos. Si la surface falta o es vacía, la operación se rechaza con `exit 2`.

**Esta es la diferencia entre un recordatorio de prompt y un compilador: uno pide por favor, el otro se niega a continuar.**

---

## ABCD — cuatro Cognitive Blueprints

Cada operación de alto impacto dispara uno de cuatro Blueprints, cada uno contrarrestando una clase específica de falla:

- **A · Axiomatic Judgment** — resuelve conflictos entre fuentes creíbles pero incompatibles. Obliga al agente a nombrar *por qué* difieren y *qué característica del contexto actual* decide.
- **B · Fence Reconstruction** — protege restricciones heredadas. Antes de remover una restricción, su *propósito original* debe ser reconstruido. **La cerca de Chesterton (Chesterton's fence)** aplicada por el sistema de archivos.
- **C · Consequence Chain** — descompone operaciones irreversibles (efecto de primer orden, de segundo orden, inversión de failure-mode, tasa base, margin of safety).
- **D · Architectural Cascade** — atrapa refactorizaciones y renombres que dejarían referencias obsoletas. Obliga al agente a enumerar el blast radius completo antes de editar.

Cada activación de un Blueprint y cada decisión que valida se registra en una **cadena hash a prueba de manipulación (tamper-evident hash chain)**. Esa cadena no es un simple log — es cómo el kernel ofrece **Active Guidance** más tarde: en la siguiente decisión coincidente, el protocolo sintetizado relevante se expone proactivamente, antes de que el agente retroceda a su distribución de entrenamiento.

El resultado: **un Thinking Framework específico de tu proyecto que se acumula**. El agente se afina con tu codebase cada vez que resuelve un conflicto — no porque lo hayas entrenado, sino porque la cadena recordó por ti.

---

## Ejecución zero-trust

El [**OWASP Top 10 for Agentic Applications (2026)**](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) — revisado por más de 100 expertos de la industria — identifica prompt injection, goal hijacking, overreach, memory poisoning y unbounded action como las principales clases de riesgo para agentes autónomos. La estructura Knowns / Unknowns / Assumptions / Disconfirmation es un contador *estructural* a cada uno:

| OWASP Agentic Risk (2026) | contador de episteme |
|---|---|
| Manipulación directa de objetivos / prompt injection | Core Question declarada antes de la ejecución; las desviaciones afloran como Unknowns |
| Inyección indirecta de instrucciones | Knowns / Disconfirmation separan el estado confiable del contenido del prompt; el agente se compromete a un resultado falsable antes de actuar sobre la entrada recuperada |
| Overreach / acción no limitada | Régimen de restricciones declarado en Frame; política reversible-first aplicada |
| Alucinación fluida | El campo Unknowns no puede quedar vacío; las suposiciones deben nombrarse antes de actuar sobre ellas |
| Envenenamiento de memoria | Protocolos Pillar 2 hash-chained — append-only, tamper-evident; reescrituras silenciosas de estado previo son detectadas por `verify_chain` |
| Bucles de planificación infinita | Condición de Disconfirmation requerida; el bucle sale cuando la evidencia se dispara |

Ninguna suposición se confía hasta ser nombrada. Ninguna acción se toma sin la precondición (Knowns) y el régimen de restricciones declarados. El kernel es la capa de verificación entre intención y ejecución.

### Convergencia industrial — 2025–2026

Frameworks y artículos académicos importantes en la misma ventana convergen sobre los mismos patrones arquitectónicos que el kernel envía: checkpoints pre-invocación a nivel del sistema de archivos ([Capsule Security ClawGuard](https://www.businesswire.com/news/home/20260415670902/), 2026), memoria hash-chained tamper-evident ([SSGM](https://arxiv.org/abs/2603.11768) — Lam et al., 2026), alineación basada en razones en lugar de listas de reglas ([Anthropic's Claude Constitution](https://www.anthropic.com/constitution), 2026-01-22), bucle cognitivo de cinco fases con capa de gobernanza ([SCL R-CCAM](https://arxiv.org/abs/2511.17673) — Kim, 2025), e integridad de agente de cinco pilares ([Proofpoint Agent Integrity Framework 2026](https://www.proofpoint.com/us/resources/white-papers/agent-integrity-framework)). El kernel precede a estas publicaciones (CP1 enviado 2026-04-21; v1.0.0 GA 2026-04-28); la convergencia es validación independiente, no linaje. Mapa completo de atribución en [`kernel/REFERENCES.md`](./kernel/REFERENCES.md) bajo *Convergent contemporary work*.

---

## Cognitive Arms — v1.1+

Los cuatro Blueprints (arriba) y los tres Pillars — Cognitive Blueprints · Append-Only Hash Chain · Framework Synthesis & Active Guidance — son la *base estructural inmóvil* de v1.0. Los Pillars no se mueven. v1.1 añade **3 Cognitive Arms** que operan encima: motores activos y fluidos que refactorizan el propio conocimiento del kernel a lo largo del tiempo.

- **Arm A · Temporal Integrity** — los protocolos decaen. El retiro confirmado por el operador supersede una regla obsoleta en lugar de sobrescribirla silenciosamente. Ventana de verificación: 30 días después de CP-DECAY-03.
- **Arm B · Causal Synthesis** — extracción de entidades sin LLM sobre el stream de deferred-discovery produce propuestas de clúster sobre las que el framework puede actuar. Ventana de verificación: 60 días.
- **Arm C · Self-Consistency Convergence** — los protocolos se promueven a modelos que derivan disconfirmaciones estructuralmente. Ventana de verificación: 90 días.

La distinción es estructural — los Pillars son vocabulario asentado; los Arms son cómo el sistema audita y refina sus propias salidas a lo largo del tiempo. Estado: **v1.4.0-rc1 cortado el 2026-05-23**, 1170 tests + 54 subtests pasando. El sustrato de Arm A ya fue enviado (infraestructura supersede-with-history + hooks de auto-instrumentación que registran ediciones de perfil de operador y de policy a streams de cadena); el residuo de Arm A se reanuda oportunísticamente. **La forma substrate-facing de Arm B fue formalmente SUNSET en Event 129** — su premisa (una brecha estable de capacidad de modelo) fue falsada por el hallazgo de saturación de los Events 119–120. Su residuo operator-facing (`core/ptsp/` typed Fact/Inference promotion gate) se conserva accesible vía `episteme practice trace`. Arm C queda scopeada para un ciclo futuro pendiente de evidencia de que la afirmación de substrate-gap sobrevive.

---

## Inicio rápido

### Opción A — Plugin de Claude Code

Dentro de Claude Code:

```
/plugin marketplace add junjslee/episteme
/plugin install episteme@episteme
```

Luego en cualquier shell:

```bash
episteme init     # sembrar archivos de memoria personal
episteme setup    # puntuar estilo de trabajo + perfil cognitivo
episteme sync     # propagar a Claude Code y Hermes
episteme doctor   # verificar conexiones
```

### Opción B — Clonar el kernel directamente

```bash
git clone https://github.com/junjslee/episteme ~/episteme
cd ~/episteme
pip install -e .

episteme init
episteme setup . --write
episteme sync
episteme doctor
```

Onboarding detallado: **[`docs/SETUP.md`](./docs/SETUP.md)**. Referencia completa de comandos: **[`docs/COMMANDS.md`](./docs/COMMANDS.md)**.

---

## Filosofía — doxa · episteme · praxis · 결

El nombre del repositorio viene del griego:

- **Doxa** (δόξα) — opinión común, la salida fluida producida por defecto. Los 11 failure modes en [`kernel/FAILURE_MODES.md`](./kernel/FAILURE_MODES.md) son una taxonomía de *doxa confundiéndose con episteme*.
- **Episteme** (ἐπιστήμη) — conocimiento justificado: Knowns concretos, Unknowns nombrados, Disconfirmation falsificable. El precondición para ejecución.
- **Praxis** (πρᾶξις) — acción informada: efectos que aterrizan con su disciplina autorizante intacta.

La palabra coreana **결** (*gyeol*) nombra el grano de la madera o piedra — el patrón latente que, seguido, produce forma coherente, y cortado en contra, se fractura. El orden de los campos de la Reasoning Surface es el *gyeol* de la disciplina epistémica: **establecido → abierto → provisional → condición de falsificación**.

---

## Lee a continuación

| Tema | Ubicación |
|---|---|
| Destilación del kernel en 30 líneas | [`kernel/SUMMARY.md`](./kernel/SUMMARY.md) |
| Dirección de diseño v1.0 RC | [`docs/DESIGN_V1_0_SEMANTIC_GOVERNANCE.md`](./docs/DESIGN_V1_0_SEMANTIC_GOVERNANCE.md) |
| Los 11 failure modes con sus contraartefactos | [`kernel/FAILURE_MODES.md`](./kernel/FAILURE_MODES.md) |
| Thinking Framework *OFF vs. ON* sobre el mismo prompt | [`demos/03_differential/`](./demos/03_differential/) |
| Cuándo el kernel es la herramienta equivocada | [`kernel/KERNEL_LIMITS.md`](./kernel/KERNEL_LIMITS.md) |
| Atribución de cada concepto prestado | [`kernel/REFERENCES.md`](./kernel/REFERENCES.md) |
| Contrato operativo del repositorio para agentes | [`AGENTS.md`](./AGENTS.md) |

---

## Por qué `episteme` — en una frase

**Postura antes que prompt (Posture over prompt).** En lugar de buscar mejor redacción, establece el *marco en el que un agente de IA piensa* a nivel del sistema de archivos. Un Thinking Framework que — como un compilador — puede negarse a continuar. No hace tu agente más inteligente; hace que esa inteligencia *aterrice en tu contexto*.

**Built as a Sovereign Cognitive Kernel — 생각의 틀**.

---

> **Note on translation.** This README is a focused-scope Spanish adaptation maintained alongside the canonical English [`README.md`](./README.md). For deepest documentation, demo walkthroughs, and architectural diagrams, refer to the English docs tree. Technical terms (Thinking Framework, Reasoning Surface, Blueprint, Core Question, Chesterton's fence, Pillar 3, flaw_classification, etc.) are kept in English because they are load-bearing kernel vocabulary.
