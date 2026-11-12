# A11yra

[![CI](https://github.com/hxrshx247-creator/A11yra/actions/workflows/ci.yml/badge.svg)](https://github.com/hxrshx247-creator/A11yra/actions/workflows/ci.yml)

A11yra helps educators find and repair common accessibility barriers in Word documents. Teachers can re-audit their changes, download the repaired DOCX, or share a learner reader with adjustable text size, line spacing, theme, and a reading ruler.

## Run locally

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

Both setups use [http://127.0.0.1:5173/](http://127.0.0.1:5173/). The defaults work without an API key or mail provider. For configuration and deployment, see [the environment template](.env.example) and [operations guide](docs/OPERATIONS.md).

## Try the four-minute demo

1. Open [Create an account](http://127.0.0.1:5173/account/signup?sample=1) to start with the built-in syllabus. The sample opens at **2 of 6 checks passed**. You can also select **Audit the sample syllabus** from a new workspace.
2. Open each finding and select **Review fix**. Set the title to `Study Group Syllabus`, the language to `en-IN`, the chart description to `Attendance doubled from 12 to 24 students`, and the link label to `Weekly study group schedule`.
3. Select **Re-audit document**, then **Run re-audit**. The sample should show **6 of 6 checks passed** and **four verified fixes**.
4. Continue to export. Open the downloaded offline HTML in your browser and try **Reading settings**. You can also publish an expiring reader link or download the repaired Word file.

The six checks cover document title, default language, headings, image descriptions, table headers, and link text. Heading findings guide edits in Word. The audit covers these checks and still needs human review of the document and its exported reading experience.

## Project layout

| Path | Contents |
| --- | --- |
| [frontend/](frontend/) | React and TypeScript app for educators |
| [backend/](backend/) | FastAPI, DOCX audit and repair, database migrations, and sample fixtures |
| [reader/](reader/) | Learner reader assets and browser tests |
| [docs/](docs/) | Setup, operations, API, and accessibility references |

The [local API reference](http://127.0.0.1:5173/api/docs) is available when the app is running. See the [document contract](A11YRA_CONTRACT.md) and [workspace and reader API](docs/PHASE-3-API.md) for details.

## Verify a checkout

From the repository root, activate the Python environment with `source .venv/bin/activate` on macOS or Linux. On Windows, use `.\.venv\Scripts\Activate.ps1` and substitute `npm.cmd` for `npm` below.

```sh
python -m pip install -r backend/requirements-dev.txt
python -m pytest backend -q
npm --prefix frontend run build
node frontend/scripts/check-contrast.mjs
```

For browser tests, install the dependencies with `npm --prefix reader ci`. On macOS or Linux, run `npx --prefix reader playwright-core install chromium`. On Windows, the runner uses Microsoft Edge by default. With ports 5173 and 8000 free, run `node reader/run-browser-tests.mjs` from the repository root. It starts isolated services and exercises the teacher workflow, public pages, and reader exports. See the [manual accessibility checklist](docs/ACCESSIBILITY-TEST.md) for screen-reader checks.
