# Frontend Versions

This directory intentionally keeps the old and new web frontends separate.

## New Web App

- Path: `frontend/workbench`
- Purpose: current Zhishiku workspace UI.
- Run:

```bash
cd frontend/workbench
npm run dev
```

- Build:

```bash
cd frontend/workbench
npm run build
```

## Legacy Web App

- Path: `frontend/legacy`
- Purpose: preserved old single-page frontend.
- Run:

```bash
cd frontend/legacy
npm run dev
```

- Build:

```bash
cd frontend/legacy
npm run build
```

## Dependency Layout

Both frontends use the shared dependency install under `frontend/node_modules`.
Do not mix source files between `legacy/src` and `workbench/src`.

## Version Management

Recommended branch convention:

- `main`: stable backend plus preserved frontend layout.
- `legacy-web`: old web app maintenance only.
- `workbench-web`: new web app development.

Before large frontend changes, create a branch from the relevant baseline and
commit only the affected frontend path.
