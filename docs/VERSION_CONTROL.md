# Version Control Plan

The project now separates old and new web code before GitHub versioning.

## Frontend Boundaries

- Legacy web app: `frontend/legacy`
- New workbench web app: `frontend/workbench`
- Shared frontend dependencies: `frontend/node_modules` (ignored by Git)

Runtime data, generated files, local databases, logs, uploads, extracted raw
materials, knowledge files, mining outputs, and writer outputs are ignored by
Git. Keep those backed up separately if needed.

## Suggested GitHub Repository

Owner: `Randy-13`

Suggested repository name:

```text
FigureLearning
```

Suggested remote URL:

```text
https://github.com/Randy-13/FigureLearning.git
```

## Branches

- `main`: stable project structure and backend.
- `legacy-web`: old frontend maintenance.
- `workbench-web`: new frontend development.

## First Push Commands

After creating the repository on GitHub:

```bash
git remote add origin https://github.com/Randy-13/FigureLearning.git
git branch -M main
git push -u origin main
```

If the repository already exists, verify the URL before pushing:

```bash
git remote -v
```
