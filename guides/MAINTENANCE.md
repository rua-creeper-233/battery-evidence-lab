# Maintenance commands

Run commands from the repository root. Maintenance modules are grouped under `maintenance/` and retain the same workflows as the earlier root scripts.

| Task | Command |
| --- | --- |
| Download or verify literature | `python -m battery_lab.fetch_literature --try-publisher` |
| Audit local full text | `python -m maintenance.audit_library` |
| Extract method evidence | `python -m maintenance.extract_method_evidence` |
| Refresh method tags | `python -m tools.build_paper_tags` |
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

For startup, use `start.bat`, `start.bat rag`, or `start.bat share`. For the local service and optional model workflow, see [RAG setup](RAG_SETUP.md) and [sharing guide](SHARING_GUIDE.md). For the search-weight workflow, see [search training](SEARCH_TRAINING.md).

The downloader validates PDF identity, title, body or supplement, page count, and SHA-256 where possible. Failed items retain their DOI entry. Automated method signals help locate evidence; they do not replace checking the original PDF. Private PDFs, manifests, Zotero identifiers, and full-text indexes remain local. Some table commands require a paper ID, source file, or other arguments; inspect `--help` before use.

## Dataset and model workflows

Metadata dataset generation reads the catalogue and authored summaries; it does not retrain a model or read private PDFs:

```powershell
python training/expand_dataset.py --insights data/paper_insights.json
python training/validate_dataset.py --train finetune/data/train.jsonl --eval finetune/data/validation.jsonl --test finetune/data/test.jsonl
python training/evaluate_model.py --eval finetune/data/test.jsonl --predictions predictions.jsonl
```

Follow [FINETUNE_INTEGRATION.md](FINETUNE_INTEGRATION.md) for QLoRA, adapter serving, and RAG connection. QLoRA answer organization and MLIP simulation training have different labels and validation criteria; a lower training loss does not establish scientific accuracy.

## Build and release verification

```powershell
python -m unittest discover -s tests
$tests = Get-ChildItem tests/test_*.mjs | ForEach-Object { $_.FullName }
node --test $tests
python -m tools.validate_research_knowledge data/research_knowledge.json
python -m tools.validate_battery_components
python -m tools.build_static_qa
python -m tools.update_project_status --date 2026-11-13
python -m tools.build_pages
python -m tools.publication_safety --public-bundle
python -m tools.publication_safety --staged
python -m tools.history_safety --no-baseline --full-inventory --scan-content
```

`docs/` is generated from authored sources. Before pushing, enable the local checks once with `git config core.hooksPath .githooks`; the hook and GitHub Actions repeat the publication and history scans. Do not stage PDFs, full-text indexes, private manifests, credentials, model weights, or local access records.
