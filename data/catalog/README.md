# Corpus catalog

`traffic-2026-08-12-v1.json` is the reviewed Phase 1B source catalog for Vietnamese road-traffic law. Every record maps to one publication page and one official PDF hosted by the Government Portal.

The catalog is versioned in Git. Downloaded PDFs, parsed JSON, and the runtime manifest remain ignored under `data/` because they are reproducible artifacts. The next phase resolves amendment relations and produces a consolidated-current view; an `amended` document is deliberately retained here so that the change history remains available.

Audit on 2026-08-12: the two law PDFs are text-native; the remaining government PDFs are image-only and therefore retained as raw provenance but require an OCR or structured-text source before they can enter retrieval. They are not counted as parsed corpus documents.
