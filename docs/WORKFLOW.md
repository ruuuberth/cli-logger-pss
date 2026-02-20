# Workflow (Native First)

## Rama base
- Base de desarrollo nativo: `main`
- Ramas web en mantenimiento: `web/main` y `web/develop`

## Convención de ramas
- `feat/<topic>`
- `fix/<topic>`
- `refactor/<topic>`
- `docs/<topic>`
- `chore/<topic>`

## Flujo diario
1. `git checkout main`
2. `git pull`
3. `./scripts/new-branch.sh feat my-change`
4. Implementar cambios
5. Commit(s) con scope claro
6. `git push -u origin <branch>`
7. Abrir PR hacia `main`

## Flujo para web (solo fixes)
1. `git checkout web/main` (o `web/develop` si aplica)
2. Crear rama de fix puntual (`fix/web-...`)
3. Abrir PR hacia la rama web correspondiente
4. No mezclar cambios web en PRs hacia `main`

## Estilo de commit sugerido
- `feat(native-ui): add ships table`
- `fix(import): skip oversized files`
- `refactor(storage): centralize db access`
- `docs(installation): update native setup`

## Reglas de PR
- Un objetivo principal por PR.
- No incluir artefactos generados (`__pycache__`, builds locales).
- Actualizar docs si cambió comportamiento.
- Verificar arranque local de app nativa antes de merge.
