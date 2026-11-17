# A11yra

[![CI](https://github.com/hxrshx247-creator/A11yra/actions/workflows/ci.yml/badge.svg)](https://github.com/hxrshx247-creator/A11yra/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-3b5b77)](LICENSE)

A11yra helps educators find and repair accessibility barriers in Word documents, then share the repaired material in a reader learners can adjust.

- **Audit six checks** for title, language, headings, image descriptions, table headers, and link text.
- **Review each repair** with a Word layout preview and a linear screen reader preview.
- **Verify changes** by running the audit again on the working copy.
- **Share the result** as a repaired Word file, offline HTML, or a learner link you can revoke.

**[Live demo][demo] · [Project report (PDF)][report] · [Submission evidence][evidence]**

## Example result

The Stacks and Queues sample went from **2 of 6 checks passed** to **6 of 6** after four verified repairs.

| Check | Before | After |
| --- | --- | --- |
| Document title | Missing | Stacks and Queues |
| Default language | Missing | English (India), `en-IN` |
| Image description | Missing | Description explains the removal order for stacks and queues |
| Link text | “click here” | Further reading on stacks and queues |

| Original screen reader preview | Repaired screen reader preview |
| --- | --- |
| ![Original preview shows a missing title and language](docs/media/screen-reader-original.png) | ![Repaired preview shows Stacks and Queues as the title and en-IN as the language](docs/media/screen-reader-repaired.png) |

[Original Word file](docs/evidence/original-lecture.docx) · [Repaired Word file](docs/evidence/repaired-lecture.docx) · [Recorded results](docs/evidence/live-results.json)

## How it works

1. **Open a DOCX.** A11yra keeps the original and creates a working copy for repairs.
2. **Review the findings.** Select a check to see what the audit found, why it matters, and what to change. Use the layout preview to locate the affected content.
3. **Apply a repair and re-audit.** A fix is marked as awaiting verification until a fresh audit checks the working copy. The comparison shows verified repairs and findings that still need review.
4. **Export or share.** Download the repaired DOCX or an offline reader, or publish a learner link. The reader offers adjustable text size, spacing, contrast, and a reading ruler.

<p align="center">
  <img src="docs/media/reader-low-vision.png" width="760" alt="Stacks and Queues learner reader with the Low vision preset, high contrast, large text, and a table of contents">
</p>

Save a copy of the [offline sample reader](docs/evidence/repaired-reader.html) and open the HTML file in a browser to try the reading settings.

## Usage

### Try the hosted demo

1. Open the [live demo][demo] and select **Try a messy handout** to start a guest audit.
2. Open the four findings and select **Review fix**. Use the values above or write your own image description and link label.
3. Choose **Re-audit document**, then **Run re-audit**. Open **View repaired screen reader view** to inspect the working copy.
4. Select **Continue to export** and download the offline HTML. Open it and try the **Low vision**, **Dyslexia-friendly**, or **Focus** preset.

### Run locally with Docker

Use Docker Compose 2.24 or newer. From the repository root, run:

```sh
docker compose up --build --wait
```

Open [A11yra](http://127.0.0.1:5173/) and choose **Try a sample audit**. The lecture opens after sign-in. Run `docker compose down` to stop the services. Docker volumes retain the local database and files. Set `VITE_SHOW_ADVANCED=true` at build time to include workspace, pricing, audit history, and account tools.

### Run locally without Docker

Use Python 3.12 and Node.js 24, the versions used in CI. This setup uses SQLite and applies migrations at startup. Run the API and frontend in separate terminals.

<details>
<summary>Windows PowerShell</summary>

API terminal, from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Frontend terminal, from the repository root:

```powershell
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run dev
```

</details>

<details>
<summary>macOS or Linux</summary>

API terminal, from the repository root:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cd backend
../.venv/bin/python -m uvicorn app.main:app --port 8000
```

Frontend terminal, from the repository root:

```sh
npm --prefix frontend ci
npm --prefix frontend run dev
```

</details>

Both setups use [http://127.0.0.1:5173/](http://127.0.0.1:5173/). The defaults work without an API key or mail provider. For configuration, see [the environment template](.env.example).

<details>
<summary>Use alternate ports</summary>

If the default ports are occupied, use the following commands after installing the dependencies. This example uses API port `8005` and Vite port `5175`.

API terminal, from `backend` (PowerShell):

```powershell
$env:A11YRA_PUBLIC_URL = 'http://127.0.0.1:5175'
$env:A11YRA_CORS_ORIGINS = 'http://127.0.0.1:5175'
..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8005
```

Frontend terminal, from the repository root (PowerShell):

```powershell
$env:A11YRA_DEV_API_PORT = '8005'
npm.cmd --prefix frontend run dev -- --port 5175
```

Open [http://127.0.0.1:5175/](http://127.0.0.1:5175/). Use that exact origin in `A11YRA_CORS_ORIGINS` so sign-in accepts requests from Vite. On macOS or Linux, use `export NAME=value` for the same variables, `../.venv/bin/python` in the API terminal, and `npm` in the frontend terminal.

</details>

## Verification

The [project report][report] records 126 passing backend tests, 12 passing browser tests, and 132 passing contrast checks. See [GitHub Actions][ci] for the latest automated results and the [manual accessibility checklist](docs/ACCESSIBILITY-TEST.md) for assistive technology checks.

<details>
<summary>Run the checks locally</summary>

Activate the Python environment with `source .venv/bin/activate` on macOS or Linux, or `.\.venv\Scripts\Activate.ps1` on Windows. Use `npm.cmd` in PowerShell.

```sh
python -m pip install -r backend/requirements-dev.txt
python -m pytest backend -q
npm --prefix frontend ci
npm --prefix frontend run build
node frontend/scripts/check-contrast.mjs
npm --prefix reader ci
```

On macOS or Linux, install the test browser with `npx --prefix reader playwright-core install chromium`. On Windows, the runner uses Microsoft Edge by default. With ports 5173 and 8000 free, run `node reader/run-browser-tests.mjs` from the repository root.

</details>

## Privacy and limitations

Uploads and working copies are private. By default, working files expire after 24 hours and audit history after 30 days. Teachers can delete uploads and revoke published reader links. See the [security notes](docs/SECURITY-NOTES.md) and [deployment guide](docs/DEPLOYMENT.md).

A11yra checks common barriers it can detect in a DOCX. Teachers still need to review reading order, the meaning of headings and descriptions, and complex content such as equations or scanned pages. The score measures the checks A11yra evaluated. WCAG conformance requires a broader review.

## Project layout

| Path | Contents |
| --- | --- |
| [frontend/](frontend/) | React and TypeScript teacher workspace |
| [backend/](backend/) | FastAPI, Word audit and repair, exports, database migrations, and sample documents |
| [reader/](reader/) | Learner reader assets and browser tests |
| [docs/](docs/) | Setup, operations, accessibility references, and [submission evidence][evidence] |

The app serves [interactive API docs](http://127.0.0.1:5173/api/docs) when running locally.

## History and credits

- The [first repository commit](https://github.com/hxrshx247-creator/A11yra/commit/79e6144) records the initial Word audit, repair, and export workflow on November 11, 2026.
- The [hackathon demo commit](https://github.com/hxrshx247-creator/A11yra/commit/c9a1732) records the sample lecture, screen reader previews, re-audit flow, and reader presets on November 12, 2026. Later commits added the formatted Word preview and finding highlights.
- A11yra uses React, Vite, FastAPI, python-docx, and Mammoth. The site bundles [Fraunces and Atkinson Hyperlegible Next](frontend/public/fonts) with their font licenses. Render hosts the demo.

[MIT license](LICENSE)

[demo]: https://a11yra-api.onrender.com/
[report]: docs/evidence/A11yra_Project_Report.pdf
[evidence]: docs/evidence/README.md
[ci]: https://github.com/hxrshx247-creator/A11yra/actions/workflows/ci.yml
