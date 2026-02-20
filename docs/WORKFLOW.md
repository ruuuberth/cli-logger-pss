# Workflow (Main-NativeApp)

## Branch policy
- Base branch: `Main-NativeApp`
- Feature branches: `feat/<topic>`
- Fix branches: `fix/<topic>`
- Refactor branches: `refactor/<topic>`
- Docs branches: `docs/<topic>`

## Daily flow
1. `git checkout Main-NativeApp`
2. `git pull`
3. `./scripts/new-branch.sh feat my-change`
4. Work and commit
5. `git push -u origin <your-branch>`
6. Open PR to `Main-NativeApp`

## Commit style
- `feat(native-ui): add battle import table`
- `fix(storage): avoid duplicate hash inserts`
- `refactor(service): split pss sync module`
- `docs(workflow): clarify branch naming`

## Rules
- One main objective per PR.
- Keep PRs small and reviewable.
- Do not commit generated local artifacts.
