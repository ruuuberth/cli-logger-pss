# Native Migration Roadmap (Actualizado)

## Objetivo

Convertir la app en un inspector de batallas sobre datos normalizados.

## Prioridades

1. Rework UI de logger:
- Lista de capturas legible para usuario (sin ruido técnico de endpoint/método).
- Cada captura abre un `Inspector Manager` con subinspectores por tabla.
- Mantener separación atacante/defensor y foco por contexto.

2. Normalización completa de replay:
- Expandir extracción de campos clave (atacante, defensor, recompensas, copas, estrellas, timestamps).
- Mantener integridad entre cabecera y tablas hijas.

3. Calidad de parsing:
- Mejorar limpieza de payload para casos con caracteres/símbolos no legibles.
- Tests de regresión sobre muestras reales.
- Fallback robusto cuando falten nodos XML parciales de replay.

4. Operación:
- Capturar flujo completo (excepto passthrough) y filtrar en capas de consumo/UI.
- Mantener crecimiento de DB acotado por retención.
