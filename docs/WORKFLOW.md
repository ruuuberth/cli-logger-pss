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

## Tipos de rama

- `feat/<topic>`
- `fix/<topic>`
- `refactor/<topic>`
- `docs/<topic>`
- `chore/<topic>`
