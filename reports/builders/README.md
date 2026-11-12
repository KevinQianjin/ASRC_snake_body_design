# Report generators

[Report index](../README.md) · [Project home](../../README.md)

The four `build_report_2026_11_*.py` scripts read saved results from `simulations/u4m2/` and write daily PDFs to `reports/daily/`. They require Python, ReportLab and the Carlito font family. Set `ASRC_REPORT_FONT_DIR` when the four Carlito TTF files are outside `/usr/share/fonts/truetype/crosextra`.

From the repository root:

```bash
python reports/builders/build_report_2026_11_11.py
```

`build_presentation_2026_11_09.js` reads the chart data and figures in this folder plus U4+M2 study figures, and writes its deck to `reports/weekly/`. It requires Node.js and `pptxgenjs`; an optional theme helper can be supplied as its first argument.

Published Word reports are in [reports/daily](../daily/). Existing publications retain their original contents; rebuilding may produce updated path references in the generated text.
