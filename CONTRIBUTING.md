# Contributing Guide

## Branch strategy

- Primary product (native app): `main`
- Legacy web maintenance branches: `web/main`, `web/develop`
- Do not mix web changes into PRs that target `main`.

## Branch naming

- `feat/<topic>`
- `fix/<topic>`
- `refactor/<topic>`
- `docs/<topic>`
- `chore/<topic>`

## Development flow (native)

1. Checkout `main`
2. Pull latest changes
3. Create a feature branch (`./scripts/new-branch.sh feat my-change`)
4. Implement and test locally
5. Open PR to `main`

## Pull request expectations

- One clear objective per PR
- Include test notes or manual verification steps
- Update docs when behavior changes
- Avoid generated artifacts (`__pycache__`, local build outputs)

## Web maintenance flow

- Use `web/main` for production hotfixes
- Use `web/develop` only when a maintenance change needs staging
- Keep web PRs isolated from native app work
