# Contributing

Use Python 3.12 and Node.js 24 to match CI. Follow the [local development setup](README.md#run-locally-without-docker), activate the virtual environment, then run these commands from the repository root. Use `npm.cmd` in Windows PowerShell if script execution is restricted.

```sh
python -m pip install -r backend/requirements-dev.txt
python -m ruff check backend
python -m pytest backend -q
npm --prefix frontend ci
npm --prefix frontend run build
node frontend/scripts/check-contrast.mjs
npm --prefix reader ci
```

Stop local servers on ports 5173 and 8000 before running the browser suite. On macOS or Linux, install Chromium with `npx --prefix reader playwright-core install chromium`. On Windows, the runner uses Microsoft Edge by default. Run `node reader/run-browser-tests.mjs` from the repository root.

Follow the surrounding Python and TypeScript style and keep contract changes in sync across the API and frontend. Run the Ruff and TypeScript checks above or install the hooks with `pre-commit install` once pre-commit is installed. Use synthetic documents and keep local environment files and generated data out of Git.
