# Browser QA — pending for current redesign

- Check desktop and narrow/mobile layouts for overflow and readable text.
- Use keyboard navigation, visible focus, and disclosure controls.
- Search a suggested query; inspect the original source passage.
- Uncheck its document, repeat search, and confirm it is absent.
- Delete a sample, restore samples, and confirm it returns.
- Import two synthetic files with the same filename; manage each separately.
- Paste text; confirm samples switch off and the new text is searched.
- Enable a sample alongside an import and search both.
- Disable every document; confirm search is disabled.
- Clear imports and confirm they are gone without changing sample choices.
- Change library selection during model loading/search; stale results must not appear.
- Open privacy and benchmark panels; verify they are adjacent on desktop.
- Verify errors, retry, model progress, and a no-results query.

Automated API tests and real-model integration passed. Browser automation returned a blank screenshot and no page accessibility tree during the current redesign, so these interaction/visual checks remain unverified.
