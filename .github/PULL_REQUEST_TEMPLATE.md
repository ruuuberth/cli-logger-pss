## Summary
- 

## Type of change
- [ ] feat
- [ ] fix
- [ ] refactor
- [ ] docs
- [ ] chore

## Scope
- Base branch expected:
  - `develop` for features/fixes/refactors/docs
  - `main` only for controlled release/hotfix promotion
- Related issue/task: 
- Temporary governance protocol acknowledged:
  - no direct push to `develop`/`main`
  - merge only via PR + CI green

## Checklist
- [ ] Branch created from `develop` (or release/hotfix branch explicitly justified)
- [ ] App runs locally (`python -m app.main`)
- [ ] Build script validated (`native_app/scripts/build.sh`) if applicable
- [ ] No temporary artifacts committed (`__pycache__`, build outputs)
- [ ] Docs updated when behavior changed
- [ ] Protocol validated: this PR is the only merge path to target branch

## Testing notes
- 

## Screenshots / Evidence (if UI change)
- 
