# Maintenance commands

Run commands from the repository root. Maintenance modules are grouped under `maintenance/` and retain the same workflows as the earlier root scripts.

| Task | Command |
| --- | --- |
| Download or verify literature | `python fetch_literature.py --try-publisher` |
| Audit local full text | `python -m maintenance.audit_library` |
| Extract method evidence | `python -m maintenance.extract_method_evidence` |
| Import Zotero records | `python -m maintenance.import_zotero_library --apply` |
| Sync Zotero links | `python -m maintenance.sync_zotero_links` |
| Attach or pull Zotero PDFs | `python -m maintenance.attach_zotero_pdf` / `python -m maintenance.pull_zotero_fulltexts` |
| Expand the paper catalogue | `python -m maintenance.expand_library` / `python -m maintenance.expand_recent_library` |
| Export RIS | `python -m maintenance.export_ris` |
| Import a Web of Science export | `python -m maintenance.import_wos <savedrecs.txt>` |
| Tune search weights | `python -m maintenance.train_search` |
| Review catalogue or Zotero metadata repairs | `python -m maintenance.repair_library_metadata --help` / `python -m maintenance.repair_zotero_metadata --help` |
| Rebuild the share card (requires Pillow) | `python -m maintenance.build_share_card` |

The repair utilities are retained for reviewed local recovery work. Inspect their help and source before running them because they can modify local metadata. Detailed audit reports are written under `private/` and are excluded from publication.

For the local service and optional model workflow, see [RAG setup](RAG_SETUP.md) and [sharing guide](SHARING_GUIDE.md). For the search-weight workflow, see [search training](SEARCH_TRAINING.md).
