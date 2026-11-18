# Manual accessibility test checklist

Use the [demo syllabus](../backend/fixtures/syllabus.docx) in Edge on Windows. Run the checks with NVDA where available. Edge DevTools’ accessibility tree can also confirm roles, names, and focus. Record browser, assistive technology, and any failures when repeating the checklist.

## Teacher workflow

- [ ] Reach **Skip to main content** first and activate it. Confirm the focus indicator remains visible.
- [ ] Upload the syllabus using the keyboard. Confirm a new audit heading receives focus and the progress announcement gives the count.
- [ ] Move among the check cards with Up and Down. Confirm the active card and its findings are announced.
- [ ] Review the image finding. Confirm the purpose controls announce their selection and the required alt-text field has a label.
- [ ] Apply a description. Confirm the status is announced. Re-audit and confirm the before-and-after counts and the verified finding.
- [ ] Download the offline HTML and HTML ZIP from the same verified audit. Confirm each filename and download message. Return to the audit to confirm it is still available.

## Learner reader

- [ ] Open the offline HTML from disk with networking disabled. Extract the ZIP and repeat with its index.html.
- [ ] Tab to **Skip to content**. Confirm **Contents**, **main**, and **Reading settings** appear as named landmarks where appropriate.
- [ ] At a narrow viewport, expand Contents with Enter or Space. Use arrow keys to move through links, then select **Attendance example**. Confirm focus moves to that heading and Contents indicates the current section.
- [ ] Tab to **Image description**, open it, and verify the complete description is available as text. Confirm decorative pictures are skipped by a screen reader.
- [ ] Read the schedule table. Confirm the caption and column headers are announced and keyboard focus can enter and leave its scroll region.
- [ ] Try 200% text size, wide spacing, dark theme, high contrast, and the spaced font. Check at 320 CSS pixels for clipping and focus visibility. Reload to check preferences where the browser permits local storage.
- [ ] Turn single-key shortcuts off. Confirm all controls still work with Tab, arrows, and Enter or Space.
- [ ] With a local voice installed, play, pause, resume, and stop. Check that the highlight follows the active text. Also confirm the status message on a device without a suitable offline voice.

Automated tests check specific behavior and markup. They cannot establish whether a learner can complete the task comfortably, whether reading order makes sense, or whether an image description conveys the right information.

## Verification coverage

Automated checks covered axe on the landing page, upload form, audit dashboard, screen reader preview, and exported reader. Browser tests checked keyboard focus, scrolling, Escape and focus return, reduced motion, reader settings, and offline use. Export tests checked document language, headings, image descriptions, decorative images, and table headers. See the [lecture verification evidence](evidence/REPORT_FACTS.md) for measured reflow and axe results.

Manual results to fill in after testing:

- **NVDA in Word and the offline reader:** Pending. Record versions and what NVDA announces for headings, images, tables, and links.
- **Actual browser zoom at 200%:** Pending. Record browser, viewport, and any clipping or focus issues.
- **Word Accessibility Checker:** Pending. Record findings and attach before-and-after screenshots for the original and repaired DOCX.
