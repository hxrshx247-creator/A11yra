# A11yra

A11yra helps teachers find and repair common accessibility barriers in Word handouts, notes, and syllabi. Phase 1 runs locally and supports born-digital DOCX files up to 10 MB.

## Run locally

From the repository root in PowerShell, install the development dependencies.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
npm.cmd --prefix frontend ci
```

Start the API and frontend in separate PowerShell terminals.

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --port 8000
```

```powershell
npm.cmd --prefix frontend run dev
```

Open [A11yra](http://127.0.0.1:5173/). If port 5173 is in use, run the frontend with `npm.cmd --prefix frontend run dev -- --port 5174` and open [port 5174](http://127.0.0.1:5174/). The [API documentation](http://127.0.0.1:8000/docs) is available while the backend is running.

## Try the teacher workflow

1. Upload [broken.docx](backend/fixtures/broken.docx). It starts at 0 of 6 checks passed.
2. Select a check and choose **Review fix**. The page explains the barrier and asks you to approve the change.
3. Fix the title, language, image description, table header, and link label. Use the original Word file when you need to see the image or table. Heading findings give instructions for Word.
4. Run a re-audit. The comparison shows **5 of 6** checks passed after all five repairs and lists the remaining heading findings.
5. Continue to export and download the working copy. A11yra reopens it with python-docx and clears the temporary server session. The export screen also lets you delete an upload.

Upload [clean.docx](backend/fixtures/clean.docx) to see the six-pass state. Use Tab and Shift+Tab to navigate, arrow keys to switch check cards, and Home or End to jump to the first or last check. The footer provides keyboard help.

## What the audit covers

| Check | What A11yra looks for |
| --- | --- |
| Title | A title in the file properties |
| Language | A default primary language tag and conflicting language tags in text |
| Headings | Missing heading styles, skipped levels, and paragraphs that may be visually styled headings |
| Images | Alt text or explicit decorative marking on supported DrawingML pictures |
| Tables | A header marker on the first row, with a note for directly bold text |
| Links | Generic labels and raw web addresses on supported hyperlinks |

**Audit progress** is the percentage of evaluated checks that passed. A check that needs review counts as evaluated. Checks with no applicable content are excluded. Review the findings and use teacher judgment before sharing any document.

Coverage is limited to the checks above. Scans, PDFs, presentations, equations, legacy pictures, and complex hyperlink fields are outside scope. The audit mainly covers the document body. It cannot judge whether descriptions are accurate, reliably recognize untagged multilingual text, or assess the complete experience of reading the handout. Heading repairs are made in Word. The learner reader and HTML export belong to Phase 2.

## Storage and API

Files live in a private operating-system temporary directory. The backend checks the file extension, MIME type, size, and Word package structure. It parses the package without executing its contents or logging document text. Each upload receives a UUID and keeps an original, a working copy, and the current audit. Use the app on loopback. The local MVP has no accounts or database.

Sessions expire 60 minutes after upload. Download and deletion close the session, and normal server shutdown clears the process's temporary directory. If the backend is force-killed, check the system temporary directory for an `a11yra-*` folder left by that process. Restarting the backend starts a new set of sessions.

| Method | Endpoint |
| --- | --- |
| GET | `/api/health` |
| POST | `/api/documents` |
| GET | `/api/documents/{id}/audit` |
| POST | `/api/documents/{id}/fixes` |
| POST | `/api/documents/{id}/reaudit` |
| GET | `/api/documents/{id}/export/docx` |
| DELETE | `/api/documents/{id}` |

The checks and repair operations are importable Python modules. The audit runner coordinates the checks, and the repair service changes the working copy. Re-audit compares the new findings with the previous audit and verifies repairs that no longer trigger their check. Downloads require applied repairs to have been evaluated again.

## Tests and fixtures

```powershell
.\.venv\Scripts\python.exe backend/scripts/make_fixtures.py
.\.venv\Scripts\python.exe -m pytest backend -q
npm.cmd --prefix frontend run build
```

The test suite covers each check, validation, repair, session cleanup, and the full API flow from a broken document to a reopened export. The teacher UI was checked in Edge with keyboard navigation, 320 px reflow, axe-core, and browser accessibility roles. Dedicated screen-reader testing remains a manual follow-up.
