# A11yra

[![CI](https://github.com/hxrshx247-creator/A11yra/actions/workflows/ci.yml/badge.svg)](https://github.com/hxrshx247-creator/A11yra/actions/workflows/ci.yml)

A11yra helps educators find and repair common accessibility barriers in Word documents. Teachers can re-audit their changes, download the repaired DOCX, or share a learner reader with adjustable text size, line spacing, theme, and a reading ruler.

**Live demo:** [a11yra-api.onrender.com](https://a11yra-api.onrender.com/)

Project references: [accessibility test](docs/ACCESSIBILITY-TEST.md) · [security notes](docs/SECURITY-NOTES.md) · [deployment](docs/DEPLOYMENT.md) · [submission evidence](docs/evidence/README.md)

## Run locally

**Fastest setup (Docker Compose):** with Docker Compose 2.24 or newer, run one command from the repository root:

```sh
docker compose up --build --wait
```

Then open [A11yra](http://127.0.0.1:5173/). After signing in, select **Try the Stack and Queue lecture** or **Try the messy handout** to see the workflow without supplying a document. Use `docker compose down` to stop the app. `VITE_SHOW_ADVANCED=true` at build time shows the workspace, pricing, audit-history and account-management areas for extended demos.

The manual Python and Node setup below is useful when you do not use Docker.

**Docker Compose** starts the web app, API, and Postgres. Use Docker Compose 2.24 or newer and run this from the repository root:

```sh
docker compose up --build --wait
```

Open [A11yra](http://127.0.0.1:5173/). Run `docker compose down` to stop the app. The local database and documents are stored in Docker volumes.

**Without Docker**, use Python 3.12 and Node.js 24, the versions used in CI. The app uses SQLite and applies migrations at startup. Run the API in one terminal and the frontend in a second.

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

### Running on alternate ports

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

**Windows:** If Application Control blocks a Python DLL, use Docker or a different environment.

## Try the four-minute demo

1. Sign in and choose **Try the Stack and Queue lecture**. Its original screen-reader view includes missing title/language, an undescribed image, and a generic link.
2. Open each finding, inspect the lecture, and approve a title, language, image description, and useful link label. The sample keeps the six-page stack-and-queue lesson content.
3. Select **Re-audit document**, then **Run re-audit**. Review the verified changes and open **View repaired screen reader view**.
4. Continue to export. Open the downloaded offline HTML and try **Reading settings** and the one-click presets.

The six checks cover document title, default language, heading structure and levels, image descriptions, table headers, and link text. The audit page includes an original/repaired linear screen-reader preview. The messy handout shows skipped heading levels, filename-style alt text, an unheaded table, vague links, and missing title/language so reviewers can see issues that require judgment.

| Original screen reader view | Repaired screen reader view |
| --- | --- |
| ![Original preview flags the missing document title and language](docs/media/screen-reader-original.png) | ![Repaired preview shows the document title and English (India) language tag](docs/media/screen-reader-repaired.png) |

![Offline learner reader with the Low vision preset selected](docs/media/reader-low-vision.png)

Demo video: [link to be added]

## Privacy and limitations

Uploaded originals, working DOCX files, and the current audit are stored in private server storage. Working files expire after 24 hours by default; audit history has a separate retention period (30 days by default). A teacher can delete a document from its audit page before expiry. Published reader links have their own expiry and can be revoked.

A11yra checks common, machine-detectable DOCX barriers; it does not certify WCAG conformance. It cannot reliably infer whether a picture is decorative, whether table cells make sense as headers, or whether a proposed heading and link label reflect the author’s intent. Teachers must inspect the source and learner reader. Complex layout, scanned documents, equations, charts, tracked changes, and non-main document stories may need manual review.

## Built during the event vs pre-existing

Fill in this section before submission so judges can distinguish event work from prior work:

- **Pre-existing:** [Add components, libraries, templates, or code that existed before the event.]
- **Built or changed during AccessED Hacks:** [Add the event-built features and the team’s contributions.]
- **Third-party assets and services:** [Add any external assets, libraries, or services used.]

## Project layout

| Path | Contents |
| --- | --- |
| [frontend/](frontend/) | React and TypeScript app for educators |
| [backend/](backend/) | FastAPI, DOCX audit and repair, database migrations, and sample fixtures |
| [reader/](reader/) | Learner reader assets and browser tests |
| [docs/](docs/) | Setup, operations, API, and accessibility references |

The [local API reference](http://127.0.0.1:5173/api/docs) is available when the app is running.

## Verify a checkout

From the repository root, activate the Python environment with `source .venv/bin/activate` on macOS or Linux. On Windows, use `.\.venv\Scripts\Activate.ps1` and substitute `npm.cmd` for `npm` below.

```sh
python -m pip install -r backend/requirements-dev.txt
python -m pytest backend -q
npm --prefix frontend run build
node frontend/scripts/check-contrast.mjs
```

For browser tests, install the dependencies with `npm --prefix reader ci`. On macOS or Linux, run `npx --prefix reader playwright-core install chromium`. On Windows, the runner uses Microsoft Edge by default. With ports 5173 and 8000 free, run `node reader/run-browser-tests.mjs` from the repository root. It starts isolated services and exercises the teacher workflow, public pages, and reader exports. See the [manual accessibility checklist](docs/ACCESSIBILITY-TEST.md) for screen-reader checks.

License: MIT ([full license text](LICENSE))
