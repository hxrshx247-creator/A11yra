# Submission evidence

| File | Contents |
| --- | --- |
| [Project report](A11yra_Project_Report.pdf) | Architecture, source excerpts, and the lecture walkthrough. |
| [Report facts](REPORT_FACTS.md) | Results and source references for the next report revision. |
| [Live results](live-results.json) | Local browser observations from the lecture repair and offline reader. |
| [Original lecture](original-lecture.docx) | DOCX input used by the recording command. |
| [Repaired lecture](repaired-lecture.docx) | Saved DOCX with title, language, image description, and link text repaired. |
| [Offline reader](repaired-reader.html) | Saved standalone HTML export of the repaired lecture. |
| [Low vision reader](reader-low-vision.png) | Screenshot of the lecture with the Low vision preset. |
| [Original screen reader view](screen-reader-original.png) | Original preview with missing title and language. |
| [Repaired screen reader view](screen-reader-repaired.png) | Working-copy preview with title and language set. |
| [Initial print PDF](reader-print.pdf) | Earlier print output from the reader. |
| [Initial print pages](reader-print-pages.png) | Image of the earlier print output. |
| [Corrected print HTML](repaired-reader-print-fixed.html) | Saved HTML used to produce the corrected print output. |
| [Corrected print PDF](reader-print-fixed.pdf) | Corrected print output from the reader. |
| [Corrected print pages](reader-print-fixed-pages.png) | Image of the corrected print output. |

## Regenerate verification results

Follow the [test setup](../../CONTRIBUTING.md). With ports 5173 and 8000 free, run this command from the repository root to replace the JSON with a fresh local browser run.

```sh
node reader/run-browser-tests.mjs record-lecture.mjs
```

The recorder uploads the saved original lecture, applies repairs through the UI, re-audits, and measures the newly downloaded offline reader. The Word files, HTML snapshots, screenshots, and print artifacts are saved submission evidence. To export a fresh reader from the saved repaired DOCX, run this command from `backend/` with the virtual environment active.

```sh
python -m scripts.export_html --reader ../docs/evidence/repaired-lecture.docx regenerated-lecture.html
```

For suite-wide counts, run the [backend, browser, and contrast checks](../../CONTRIBUTING.md).
