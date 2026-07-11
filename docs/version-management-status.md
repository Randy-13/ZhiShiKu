# Version Management Status

Last checked: 2026-07-08

## Current Repository State

- Current branch: `codex/xhs-image-text-workspace`
- Remote `origin`: `https://github.com/Randy-13/ZhiShiKu.git`
- The worktree is not clean. There are many existing uncommitted changes across backend, frontend, tests, settings, media parsing, and Xiaohongshu files.
- Untracked files seen during the check:
  - `docs/web-api-model-map.md`
  - `tools/run_douyin_downloader.ps1`

## Versioning Decision

Because the repository already contains broad uncommitted work, do not create a mixed catch-all commit without an explicit decision. The safer options are:

- Review and commit the existing feature work as one or more named commits.
- Create a separate documentation-only commit containing only help/versioning docs.
- Keep the current worktree as-is and continue editing without committing.

## Files That Must Stay Out Of Git

Never commit cookies, local databases, generated media, screenshots, local secrets, `auth/`, `.env`, or runtime data directories. In this project that includes user data such as:

- `knowledge/`
- `images/`
- `documents/`
- `media/`
- `writer/`
- `raw_materials/`
- `knowledge.db`
- `auth/`

## Suggested Pre-Push Validation

Run the relevant checks before pushing a completed version:

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py tests\test_app_api.py
.\.venv\Scripts\python.exe -m pytest tests\test_app_api.py
.\.venv\Scripts\python.exe -m pytest tests\test_media_parser.py -q
cd frontend\workbench
npm.cmd run build
cd ..\..
.\.venv\Scripts\python.exe tools\check_encoding.py
```

If only documentation changed, the encoding check is usually the most relevant lightweight verification.
