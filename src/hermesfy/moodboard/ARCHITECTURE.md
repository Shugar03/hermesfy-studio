# Moodboard Engine para Hermesfy

## Inspiración: Higgsfield AI Moodboard
Higgsfield permite crear un "moodboard" con imágenes de referencia que definen
la estética deseada (paleta, mood, iluminación, composición) y luego genera
con esa línea estética consistente.

## Arquitectura Propuesta

```
USUARIO: "moodboard para hotel de lujo en la selva"
         │
         ▼
┌─────────────────────┐
│  BRAVE IMAGE SEARCH  │  ← API key ya configurada
│  "luxury jungle spa" │
└─────────┬───────────┘
          │ 15-20 image URLs
          ▼
┌─────────────────────┐
│  DOWNLOAD + CURATE   │  ← filtrar duplicados, baja calidad
│  8-12 imágenes       │
└─────────┬───────────┘
          │ imágenes locales
          ▼
┌─────────────────────┐
│  ANALYZE (VRH) x12  │  ← VisualAnalyzer a cada una
│  12 StructuredSpecs  │     (paleta, mood, luz, composición)
└─────────┬───────────┘
          │ 12 specs individuales
          ▼
┌─────────────────────┐
│  MOOD SYNTHESIZER   │  ← NUEVO: sintetizar spec unificado
│  MOOD_SPEC único    │     • Paleta: colores más repetidos
└─────────┬───────────┘     • Mood: el más frecuente
          │                 • Composición: patrones comunes
          ▼                 • Iluminación: consenso
┌─────────────────────┐
│  SPECBRIDGE + HERMESFY│
│  Generar imagen final │
└─────────────────────┘

Output: imagen con la estética unificada del moodboard
```

## Lo que ya tenemos (funciona)
✅ Brave Image Search API (key configurada, probada)
✅ VisualAnalyzer → StructuredSpec
✅ SpecBridge + Goldilocks Rule
✅ Hermesfy DAG → Fal.ai

## Lo que falta crear
❌ `moodboard/` module con:
   - `searcher.py` — Brave Image Search wrapper
   - `curator.py` — Descarga + filtro de imágenes
   - `synthesizer.py` — Unificar N specs en un MOOD_SPEC único
   - `moodboard.py` — Orquestador del pipeline completo
❌ Tool `hermesfy_moodboard` registrada en plugin.py
❌ Skill `hermesfy-moodboard` para el agente

## Cómo se sintetiza el MOOD_SPEC
- **Paleta**: top 6 colores HEX más repetidos entre todas las imágenes
- **Gradiente**: el más común entre los specs
- **Mood**: modo (mayoría) de moods detectados
- **Técnica**: modo de técnicas
- **Iluminación**: tipo y dirección más comunes
- **Composición**: regla más frecuente
- **Semántica**: se toma la descripción del usuario (no de las imágenes)
