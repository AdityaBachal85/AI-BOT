# Put company documents in this folder

Anything you place here becomes searchable by the assistants after you run:

    docker compose run --rm setup

Works with: PDF (with real text, not scans), Word (.docx), Excel (.xlsx), PowerPoint (.pptx),
CSV, plain text (.txt), Markdown (.md) and HTML.

Tips
- Sub-folders are fine, for example `hr/`, `projects/sunrise-heights/`, `sales/`.
  The folder name becomes part of the document's location in the app.
- Files whose names start with `_` or `.` are ignored (like this one).
- Re-run the setup command after adding, changing or deleting files. Only the changes are processed.
- Scanned PDFs (pictures of pages) contain no text and will be reported as "could not be read".
  Open them in a PDF tool with OCR and save a text version first.
- This folder is not uploaded to GitHub (see `.gitignore`). Keep a backup elsewhere.
