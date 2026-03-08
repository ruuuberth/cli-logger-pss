# Contributing

## Scope del proyecto

Este repositorio prioriza la app nativa de replay logger en `native_app/`.

## Branch strategy

- Base de desarrollo: `develop`
- Base de release: `main`
- PRs nativos: hacia `develop`

## Branch naming

- `feat/<topic>`
- `fix/<topic>`
- `refactor/<topic>`
- `docs/<topic>`
- `chore/<topic>`

## Expected flow

1. `git checkout develop && git pull --ff-only`
2. Crear rama
3. Implementar cambio + pruebas locales
4. Actualizar docs si cambia comportamiento
5. Abrir PR con alcance único

## PR checklist

- Cambios acotados a un objetivo
- Sin artefactos generados
- Notas de validación incluidas
- Si toca captura/normalización: incluir pruebas o evidencia de verificación
