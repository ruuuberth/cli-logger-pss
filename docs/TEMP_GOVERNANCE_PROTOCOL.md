# Protocolo Temporal de Gobernanza

Aplica mientras el repositorio siga privado sin branch protection nativa de GitHub.

Objetivo: simular branch protection por proceso para evitar pushes directos a `develop` y `main`, mantener CI verde y releases confiables.

## Reglas obligatorias

1. `develop` es integración de desarrollo.
2. `main` es producción estable.
3. No se permite push directo a `develop` ni `main`.
4. Todo cambio entra por PR.

## Flujo estándar

1. `git checkout develop && git pull --ff-only`
2. Crear rama: `feat/...`, `fix/...`, `refactor/...`, `docs/...`, `chore/...`
3. Implementar y validar localmente.
4. Abrir PR a `develop`.
5. Merge solo con checklist completo y CI verde.

## Regla de PR (no negociable)

Un PR se puede mergear solo si cumple:

- PR a `develop`: `Native Tests` (pytest) en verde, además del secret scan (gitleaks).
- PR a `main`: `Native Build` Linux y Windows en verde (además del secret scan).
- Plantilla de PR completa.
- Al menos una aprobación manual.
- Sin conflictos y sin commits WIP.

## Protocolo de release

### Pre-release (canal de pruebas)

- Trigger: push a `develop`.
- Estado actual: **deshabilitado** (`prerelease-develop.yml.disabled`).
- Assets que publicaría al reactivarse:
  - `pss-logger-native-linux-portable.zip`
  - `pss-logger-native-windows-portable.zip`
  - `SHA256SUMS.txt`
  - `SHA256SUMS.txt.asc` (solo si hay firma)

### Release estable

1. PR `develop -> main` (sin excepciones).
2. CI de ese PR en verde.
3. Merge a `main`.
4. Crear tag sobre `main`:
   - `git tag vMAJOR.MINOR.PATCH`
   - `git push origin vMAJOR.MINOR.PATCH`
5. Validar workflow `Native Release` y assets/checksum.

## Controles manuales

### Diario (2 min)

- Revisar `git log` en `develop` y `main` para confirmar que no hubo push directo.
- Revisar Actions recientes por fallos de release/pre-release.

### Semanal (10 min)

- Verificar uso de PR template e issue forms.
- Revisar últimos releases/pre-releases y checksum.
- Auditar que tags `v*` correspondan a commits de `main`.

## Escalación y excepciones

- Hotfix urgente:
  - permitido solo con PR abreviado + CI verde.
  - documentar motivo de urgencia en el PR.
- Si alguien hace push directo:
  - revertir por PR correctivo.
  - registrar incidente en issue interno.
  - restablecer regla estricta inmediatamente.

## Checklist operativo

### Antes de merge a `develop`

- [ ] PR abierto desde rama feature/fix/refactor/docs/chore
- [ ] `Native Tests` (pytest) en verde
- [ ] Secret scan (gitleaks) verde
- [ ] aprobación manual
- [ ] documentación actualizada si aplica

### Antes de tag estable

- [ ] `develop -> main` mergeado por PR
- [ ] CI en verde en PR a `main`
- [ ] tag `v*` creado sobre `main`
- [ ] release con binarios + `SHA256SUMS.txt` validado

## Protocolo post-history-rewrite

Si se reescribe historial por saneamiento de secretos:

- Recomendado: re-clone completo del repositorio.
- Alternativa:
  - `git fetch --all --prune`
  - `git checkout develop && git reset --hard origin/develop`
  - `git checkout main && git reset --hard origin/main`
- No hacer push desde clones antiguos hasta resincronizar.

## Criterio de salida

Este protocolo se reemplaza por branch protection nativa cuando exista plan de GitHub que permita:

- Require pull request before merge
- Required status checks
- Block direct push
- Dismiss stale approvals
