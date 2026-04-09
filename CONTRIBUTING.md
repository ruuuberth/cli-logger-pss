# Contributing

## Scope del proyecto

Este repositorio prioriza la app nativa de replay logger en `native_app/`.

## Branch strategy

- Base de desarrollo: `develop`
- Base de release: `main`
- PRs nativos: hacia `develop`
- Sin GitHub branch protection activa: no se permite push directo a `develop` ni `main` (regla operativa obligatoria).

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

## CI/CD contract

- PR hacia `develop` o `main`:
  - ejecuta `Native Build` (Linux + Windows) como control de calidad.
- Push a `develop`:
  - ejecuta `Native Pre-release (develop)` y actualiza `develop-latest`.
- Push de tag `v*`:
  - ejecuta `Native Release` y publica release estable.

## Stable release process

1. Asegurar que `develop` esté validado y fusionado en `main` por PR.
2. Crear tag sobre `main`:
   - `git tag vMAJOR.MINOR.PATCH`
   - `git push origin vMAJOR.MINOR.PATCH`
3. Verificar assets y checksums en GitHub Releases.

## Protocolo temporal (repo privado sin branch protection)

Mientras no exista GitHub Pro/Team en este repo privado, aplica el protocolo temporal:

- Documento oficial: `docs/TEMP_GOVERNANCE_PROTOCOL.md`
- Regla clave: todo cambio entra por PR.
- Excepción hotfix: solo por PR abreviado con CI verde y motivo documentado.

## PR checklist

- Cambios acotados a un objetivo
- Sin artefactos generados
- Notas de validación incluidas
- Si toca captura/normalización: incluir pruebas o evidencia de verificación

## Seguridad

- No commitear archivos `.env` reales.
- Solo se aceptan `.env.example` y `.env.dev.example`.
