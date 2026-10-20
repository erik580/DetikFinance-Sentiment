# old/ — Arsip versi lama (berbasis modul `src/`)

Folder ini berisi **versi lama** pipeline, yang memakai modul Python di `src/` dan notebook
yang mengimpornya. Diarsipkan pada saat beralih ke pendekatan **notebook self-contained**
(satu `.ipynb` mandiri per fase, tanpa `import src`).

- `old/src/` — modul lama (crawl, parse, clean, tiering, segment, link, topics, ...)
- `old/notebooks/` — notebook lama (00–06) yang mengimpor `src/`
- `old/scripts/` — skrip lama

**Versi yang DIPAKAI sekarang** ada di folder `notebooks/` (root), berupa notebook
self-contained. Folder `old/` disimpan hanya sebagai referensi/riwayat.
