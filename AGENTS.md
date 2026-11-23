# Agent Guide

## Project context

- Read `spec.md` before making project changes.
- The project is a Python/Tkinter desktop beam designer.
- Keep beam calculations independent of the UI; use Tkinter Canvas for diagrams.
- `spec.md` is authoritative. `index.html` is a behavioral reference, not the desktop implementation.
- The desktop app uses US customary units only; do not port the HTML metric toggle unless requested.
- Keep changes within the scope of the user's request.

## Prompt log

Keep this log up to date as work is requested. Add concise entries containing the user's request and the resulting action or decision. Do not include private information.

### 2026-11-23

- Request: “can we make a agent md and index.html”
  - Clarification: `index.html` is a reference for app behavior; keep the Tkinter desktop app as the target.
- Request: “Make an `AGENTS.md` so the agent keeps a prompt log for this project too.”
  - Action: Created this file with project guidance and a prompt log. No other files changed.
- Request: Add a beam validation case and build the app described in `spec.md`.
  - Clarification: The project is a beam designer; use US customary units and Tkinter Canvas diagrams.
  - Action: Planned a pure calculation module, Tkinter UI and diagrams, automated validation tests, and project documentation.
- Request: “make it so loads can only be on the beam itself”
  - Decision: Constrain load controls to the current span and move existing coordinates to the new beam end when the span shrinks.
- Request: Run Step 1, Save and Open.
  - Action: Added versioned JSON save/open, file-menu commands, and tests for round trips and invalid files.
- Request: Run Step 2, Export results.
  - Action: Added CSV export with unit-labeled columns and duplicate rows at point-load shear jumps.
- Request: Run Step 3, Calculation sheet.
  - Action: Added a PDF report using ReportLab with beam inputs, loads, diagrams, reactions, and checks.
- Request: Write a short README with app purpose, install packages, and launch command.
  - Action: Condensed README.md to those essentials.
