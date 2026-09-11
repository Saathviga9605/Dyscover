# Legacy migration

The original files remain in the repository as a reference implementation.

| Legacy surface | Stage 1 destination |
| --- | --- |
| `index.html`, `about.html`, `contact.html` | React public routes |
| `screening.html` | Child assessment entry shell |
| `level1.html` visual confusion and mirror tasks | Modular game definitions; Stage 2 activity |
| `level2.html` sequencing and word maze | Modular game definitions; Stage 2 activity |
| WebGazer calibration/fixation code | `gaze/types.ts` boundary and future backend gaze models |
| CSV research columns | Trial features and future research export |
| `sample_report.html` | Parent report architecture, with no fake results |
| duplicated Lexi/chatbot markup | `LexiWidget` and future service interface |
| legacy CSS, Tenor, Chart.js, pixel fonts | New tokenized design system |

Important legacy defects are intentionally not copied: fixed 800x600 geometry, hard-coded score-to-probability logic, duplicate chatbot IDs, unsafe `innerHTML`, missing `script.js` references, duplicated external scripts, and unflushed/faulty CSV paths.
