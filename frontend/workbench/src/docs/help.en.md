# Zhishiku Help

## Quick Start

Zhishiku organizes the knowledge workflow into six main workspaces: Collect, Learn, Mine, Create, Library, and Settings. The safest path is to save external material as an original first, generate focus knowledge from originals, then mine perspectives or create content.

- Collect: turn text, images, files, media, or links into editable originals.
- Learn: select original files and generate focus knowledge drafts.
- Mine: select originals and a perspective, then generate RTFC interpretations.
- Create: use library files to move through topics, draft, revision, images, design, and preflight.
- Library: edit Markdown files in Originals, Focus, and Perspectives.
- Settings: check APIs, OCR, ASR, image settings, Bilibili cookies, and storage.

[Open Collect](#/collect) [Open Settings](#/settings)

## Material Collection

Collect has one job: convert external material into originals. Text, screenshots/images, documents, media, and links all enter the same material queue.

### Recommended Flow

- Choose the material type, then enter text, upload files, or paste links.
- Check the title, source, status, and nearby error message in the queue.
- Generate an original draft, then review the title, note, and Markdown body.
- Save to Originals. Saving does not automatically learn knowledge or start creation.

### Link Material

Regular web links use real extraction. Platform or video links such as Bilibili, Douyin, and Xiaohongshu should use the media or platform parser path instead of being treated as plain text.

[Open Collect](#/collect)

## Knowledge Learning

Learn turns originals into reusable focus knowledge. Sources must come from original files selected in the right library rail.

### Recommended Flow

- Switch the right library rail to Originals.
- Select one or more original files.
- Add them to the learning queue, then generate focus knowledge.
- Review the title, note, and body, then commit the draft to Focus.

### Notes

Generated knowledge still needs human review. Do not commit drafts that lack sources, context, or readable structure.

[Open Learn](#/learn)

## Perspective Mining

Mine reads originals through specific perspectives and saves the result to Perspectives. The page keeps lens management on the left and interpretation on the right.

### Lens Fields

- Name: who is reading.
- Positioning: what the lens pays attention to.
- Core goal: what judgment this pass should produce.
- Stance: the default standard and evaluation bias.

### Output Structure

Interpretations follow RTFC and produce five sections: stance and standard, source extraction, dedicated analysis, risks and questions, and conclusion.

[Open Mine](#/mine)

## Content Creation

Create links knowledge confirmation, topic selection, drafting, revision, images, design, preflight, and publishing into one project flow. Projects should cite saved library files instead of temporary copied fragments.

### Recommended Flow

- Select original, focus, or perspective files from the right library rail.
- Create or select a writing project.
- Generate topic options, choose one, then generate a draft.
- Revise the draft, then handle images, design, and preflight.
- Before publishing, check digest length, images, HTML, and platform limits.

If image generation partly fails, successful images should remain available. If preflight finds an overlong digest, it should be shortened to the platform limit.

[Open Create](#/create)

## Library Management

The Library contains Originals, Focus, and Perspectives. The main area is a file editor for title, note, and Markdown body.

### Saving Rules

- If a list item only has metadata, selecting it loads the full Markdown.
- Saving writes through the backend and updates the Markdown file.
- Originals store readable source material, Focus stores distilled knowledge, and Perspectives store lens-based interpretations.

Do not manually delete runtime knowledge files. Use the UI or backend deletion flow.

[Open Library](#/library)

## Settings And Dependencies

Settings manages language, text extraction mode, API settings, local storage, and the global runtime log. Dependency checks include Bilibili cookie status.

### Bilibili Cookies

Bilibili subtitle extraction prefers the Netscape cookie file pointed to by `FIGURELEARNING_YTDLP_COOKIES_FILE`. The default file is `auth/bilibili.cookies.txt`, which must not be committed.

Settings checks whether the file exists, is readable, and contains `SESSDATA`, `DedeUserID`, and `bili_jct`. Actual subtitle availability is verified when extraction runs in Collect.

[Open Settings](#/settings)

## Troubleshooting

### Disabled Buttons

Disabled buttons should show a nearby reason. Common causes include no selected source, wrong library bucket, missing Markdown path, unavailable API settings, or a running background task.

### Generation Failed

Check the material queue or global runtime log first. Then verify API settings, network access, Bilibili cookies, uploaded files, and Markdown read/write access.

### Page State Looks Wrong

Refresh the page and reselect the workspace and file. If the issue remains, avoid manually editing the database or runtime directories; use the UI to regenerate or save again.

[Open Settings](#/settings)
