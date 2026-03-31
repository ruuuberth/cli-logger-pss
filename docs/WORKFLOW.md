# Workflow

## Ramas

- Desarrollo nativo: `develop`
- Release: `main`
- Web legado: `web/main`, `web/develop`

## Flujo diario (native)

1. `git checkout develop`
2. `git pull --ff-only`
3. `git checkout -b feat/<topic>`
4. Implementar + probar (`pytest -q`)
5. `git push -u origin <branch>`
6. Abrir PR a `develop`

## Regla operativa temporal (sin branch protection)

- Prohibido push directo a `develop` y `main`.
- Merge solo por PR con CI verde.
- Para detalle operativo completo ver: `docs/TEMP_GOVERNANCE_PROTOCOL.md`.

## Flujo de release (estable)

1. PR de promoción: `develop -> main`.
2. CI verde en ese PR.
3. Merge a `main`.
4. Crear tag `vMAJOR.MINOR.PATCH`.
5. Push del tag para disparar `Native Release`.

## Tipos de rama

- `feat/<topic>`
- `fix/<topic>`
- `refactor/<topic>`
- `docs/<topic>`
- `chore/<topic>`
