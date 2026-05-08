# SPEC: Hermesfy V5 — Chat Agent + Live Canvas

> **Inspired by:** Nebula Nodes / Daedalus (Justin Perea, Hermes Creative Hackathon 2026)
> **Analysis date:** 2026-05-08
> **Status:** SPEC — pending implementation

---

## §1 — Contexto

Hermesfy V4 tiene un DAG engine sólido (Kahn's topological sort, BudgetGate, SeedPropagator, genmedia provider) y un dashboard vanilla HTML/CSS. Pero carece de:

1. **Chat agent** que construya DAGs desde lenguaje natural
2. **Canvas sync en vivo** (WebSocket) entre backend y frontend
3. **Multi-provider** (solo FAL vía genmedia)
4. **Streaming** de outputs durante ejecución
5. **Learnings discipline** (bugs → memoria persistente)

Nebula Nodes / Daedalus resolvió todo esto con una arquitectura elegante de 5 patrones clave. Esta SPEC adapta esos patrones a Hermesfy.

---

## §2 — Lo que Nebula Nodes hace bien (y nosotros no)

### Patrón 1: Hermes Agent como SUBPROCESS

```python
# No API REST — subprocess directo
proc = await asyncio.create_subprocess_exec(
    "hermes-daedalus", "chat", "-q", message,
    "--provider", "nous",
    "--model", "moonshotai/kimi-k2.6",
    "--skills", "daedalus-core",
    stdout=PIPE
)
```

**Por qué funciona:**
- Profile isolation: `hermes-daedalus` es un alias que aísla SOUL.md + skills + memories del perfil global
- Sin overhead de API REST — comunicación directa vía stdout/stderr
- El backend solo parsea output, no necesita conocer el modelo

### Patrón 2: Canvas Sync via CLI → HTTP → WebSocket

```
Daedalus: terminal("nebula create text-input")
    → POST /api/graph/node  (FastAPI)
    → broadcast graphSync   (WebSocket)
    → React Flow re-render  (frontend)
```

Cada tool call de Hermes Agent golpea el backend HTTP, que emite `graphSync` WS events al canvas.

### Patrón 3: Streaming Multi-Canal

Tres fuentes de streaming en paralelo:
- **stdout del subprocess** — verbose mode de Hermes (prose boxes)
- **agent.log tailer** — heartbeats durante silencios del modelo
- **HTTP action taps** — `publish_action()` en cada endpoint del backend

### Patrón 4: Narrator Fallback

Kimi K2.6 bug: emite `content: ""` + `tool_calls`. El fallback traduce las tool calls buferizadas → texto narrativo vía OpenRouter.

### Patrón 5: Learnings Discipline

```
SKILL.md §5:
  Al inicio: skill_view daedalus-learnings/LEARNINGS.md
  Al final:  skill_manage patch daedalus-learnings/LEARNINGS.md
  + stdout:  LEARNING_SAVED: slug
```

---

## §3 — Arquitectura Propuesta para Hermesfy V5

```
┌──────────────────────────────────────────────────────────────┐
│                     HERMESFY V5                               │
│                                                               │
│  Frontend (Vite + React)        Backend (FastAPI)             │
│  ┌───────────────────┐        ┌───────────────────────┐       │
│  │ React Flow Canvas  │◄──WS──│  /ws/chat              │       │
│  │ ChatPanel          │       │  /ws/execution         │       │
│  │ DAG Inspector       │       │  POST /api/dag/*       │       │
│  │ Model Picker       │       │  POST /api/chat        │       │
│  └───────────────────┘        └───────┬───────────────┘       │
│                                        │                       │
│                             ┌──────────▼──────────┐            │
│                             │  hermes_session.py   │            │
│                             │  (NUEVO — wrapper)   │            │
│                             │  ┌────────────────┐  │            │
│                             │  │ subprocess:     │  │            │
│                             │  │ hermes-hermesfy │  │            │
│                             │  │ chat -q         │  │            │
│                             │  │ --skills        │  │            │
│                             │  │  hermesfy-agent │  │            │
│                             │  └───────┬────────┘  │            │
│                             │          │            │            │
│                             │  ┌───────▼────────┐  │            │
│                             │  │ Verbose Parser  │  │            │
│                             │  │ + Log Tailer    │  │            │
│                             │  │ + Action Taps   │  │            │
│                             │  └───────┬────────┘  │            │
│                             └──────────┼───────────┘            │
│                                        │                       │
│  ┌─────────────────────────────────────▼─────────────────────┐ │
│  │                    HERMES AGENT                            │ │
│  │  Profile: hermesfy (NUEVO)                                │ │
│  │  ┌──────────────────────────────┐                         │ │
│  │  │ SOUL.md — Hermesfy persona   │                         │ │
│  │  │ hermesfy-agent/SKILL.md      │ ← playbook del agente   │ │
│  │  │ hermesfy-learnings/LEARNINGS │ ← bugs → memoria        │ │
│  │  └──────────────────────────────┘                         │ │
│  │                                                            │ │
│  │  Tools:                                                    │ │
│  │    terminal("hermesfy create/edit/upscale ...")            │ │
│  │    hermesfy_define_workflow(...)                           │ │
│  │    hermesfy_execute_workflow(...)                          │ │
│  │    hermesfy_workflow_status(...)                           │ │
│  │    vision_analyze(...)                                     │ │
│  │    skill_manage(...)            ← learnings discipline     │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## §4 — Plan de Implementación (por fases)

### FASE 0: Perfil Hermesfy + CLI (1 día)
- [ ] Crear perfil `hermesfy` con SOUL.md
- [ ] Crear skill `hermesfy-agent/SKILL.md` (playbook del agente)
- [ ] Crear CLI wrapper: `hermesfy create/edit/upscale ...` → POST al backend
- [ ] Alias: `hermes profile alias hermesfy --name hermes-hermesfy`

### FASE 1: Subprocess Wrapper (1 día)
- [ ] `backend/services/hermes_session.py` — spawn `hermes-hermesfy chat -q`
- [ ] `backend/services/hermes_verbose_parser.py` — parsear prose boxes de Hermes
- [ ] `backend/services/chat_actions.py` — event bus para action taps
- [ ] Log tailer con heartbeats (20s quiet window)

### FASE 2: WebSocket + Canvas Sync (1 día)
- [ ] `POST /api/dag/node` — crear/editar nodos desde CLI
- [ ] `POST /api/dag/edge` — conectar nodos
- [ ] `POST /api/dag/execute` — ejecutar workflow
- [ ] WebSocket `/ws/dag` — broadcast `dagSync` events
- [ ] WebSocket `/ws/chat` — streaming de chat events

### FASE 3: Chat Agent Skill (1 día)
- [ ] `hermesfy-agent/SKILL.md`:
  - Hard rule: narrate in `content`, not `reasoning_content`
  - Iterative loop: plan → build ONE stage → inspect → iterate (max 3)
  - CLI cookbook: `hermesfy nodes`, `hermesfy graph`, `hermesfy create/connect/run`
  - Pipeline stage tracing (canonical stages by medium)
  - Vision reliability rules
  - Learnings discipline

### FASE 4: Narrator Fallback (½ día)
- [ ] Detectar `content: ""` + `tool_calls` (Kimi bug)
- [ ] `backend/services/narrator.py` — sintetizar texto narrativo de acciones

### FASE 5: Learnings Discipline (½ día)
- [ ] `skill_manage patch hermesfy-learnings/LEARNINGS.md` al final del turno
- [ ] `skill_view hermesfy-learnings/LEARNINGS.md` al inicio
- [ ] Formato: `[DATE slug] Observed: / Fix: / Confidence: low|medium|high`

### FASE 6: React Flow Frontend (2 días)
- [ ] Migrar de vanilla HTML a React 19 + Vite
- [ ] React Flow canvas con nodos tipados y coloreados
- [ ] ChatPanel con streaming en vivo
- [ ] AgentLog panel (thinking stream)
- [ ] Daedalus-style dual-tone theme

### FASE 7: Multi-Provider (1 día)
- [ ] Universal nodes: OpenRouter, Nous Portal, Replicate
- [ ] Proxy routes como Nebula Nodes (`/api/openrouter/proxy`, etc.)
- [ ] BYOK settings panel

---

## §5 — Contratos Técnicos

### 5.1 CLI Hermesfy (comandos que Daedalus usa via terminal())

```bash
hermesfy nodes                    # listar tipos de nodo disponibles
hermesfy info <definition_id>     # schema de un tipo de nodo
hermesfy graph                    # estado actual del DAG
hermesfy context                  # vista compacta del DAG
hermesfy create <type> [--param k=v]  # agregar nodo
hermesfy connect <src>:<port> <dst>:<port>  # conectar nodos
hermesfy set <node_id> <key>=<value>  # editar params
hermesfy run <node_id>            # ejecutar nodo + upstream
hermesfy run-all                  # ejecutar DAG completo
hermesfy save <file>              # persistir DAG
hermesfy load <file>              # cargar DAG
hermesfy clear                    # limpiar DAG
```

### 5.2 WebSocket Events

```typescript
type DAGSyncEvent = {
  type: 'dagSync';
  nodes: DAGNode[];
  edges: DAGEdge[];
  execution?: NodeStates;
};

type ChatEvent =
  | { type: 'session'; sessionId: string }
  | { type: 'text'; text: string }
  | { type: 'thinking'; text: string }
  | { type: 'approval_request'; summary: string; plan?: string; cost?: string }
  | { type: 'learning_saved'; topic: string }
  | { type: 'error'; message: string }
  | { type: 'done' };
```

### 5.3 Hermes Profile Contract

```yaml
# ~/.hermes/profiles/hermesfy/
├── SOUL.md           # "You are Hermesfy — DAG craftsman for AI image pipelines"
├── skills/           # symlinks a hermesfy-agent/SKILL.md
├── memories/         # learnings auto-populadas
└── logs/agent.log    # tailed por el backend
```

### 5.4 Budget Gate (mantener existente + mejorar)

```python
# Mantener BudgetGate de V4 pero con:
# - Per-turn budget (no solo per-flow)
# - Multi-model cost estimation (FAL, OpenRouter, Replicate, Nous)
# - Approval request cuando el costo supera umbral
```

---

## §6 — Métricas de Éxito

| Métrica | V4 Actual | V5 Target |
|---------|-----------|-----------|
| Plain-language → DAG ejecutado | ❌ Manual builder | ✅ Chat agent construye en <3 turns |
| Canvas sync | ❌ Static reload | ✅ <500ms WS latency |
| Modelos disponibles | 22 (FAL) | 300+ (multi-provider) |
| Streaming durante ejecución | ❌ | ✅ Triple canal |
| Errores → memoria | ❌ | ✅ Auto-documentados |
| Timeout UX | 360s silent | Heartbeats + progress |

---

## §7 — Riesgos

| Riesgo | Mitigación |
|--------|-----------|
| Kimi K2.6 `content: ""` bug | Narrator fallback (FASE 4) |
| Latencia de subprocess | Log tailer + heartbeats (FASE 1) |
| Complejidad de React Flow | Empezar con vanilla mejorado, migrar en FASE 6 |
| Multi-provider auth | BYOK settings panel (FASE 7) |
| Budget en multi-provider | Estimación por modelo en BudgetGate |

---

## §8 — Referencias

- **Nebula Nodes source:** `https://github.com/JustinPerea/nebula-nodes`
- **Key files analizados:**
  - `backend/services/hermes_session.py` — subprocess wrapper (522 LOC)
  - `backend/services/hermes_verbose_parser.py` — parser de stdout (245 LOC)
  - `backend/services/chat_actions.py` — event bus (112 LOC)
  - `backend/services/narrator.py` — Kimi fallback
  - `.hermes/profiles/daedalus/SOUL.md` — persona (9 LOC)
  - `.hermes/skills/daedalus-core/SKILL.md` — playbook (348 LOC)
  - `frontend/src/components/panels/ChatPanel.tsx` — chat UI (1713 LOC)
  - `frontend/src/lib/wsClient.ts` — WebSocket client (84 LOC)
- **Modelo:** `moonshotai/kimi-k2.6` via OpenRouter / Nous Portal
- **Hackathon:** Hermes Agent Creative Hackathon 2026
