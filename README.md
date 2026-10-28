# Battery Evidence Lab

Battery Evidence Lab is a local-first research assistant for battery-materials work. It organizes traceable paper evidence, provides static learning pages and rule-based answers, and can connect to a local retrieval service. It covers DFT, VASP, NEB, AIMD, molecular dynamics, and machine-learning interatomic potentials.

Public entry point: <https://rua-creeper-233.github.io/battery-evidence-lab/>

The repository and website expose selected bibliographic metadata, guides, and generated static pages. Local PDFs, private Zotero records, access records, API keys, model weights, and other private context stay local.

![System overview: static pages in a browser can stand alone or connect to a local retrieval service and an optional language-model endpoint.](static/assets/docs/system-overview.svg)

## Start here

| Need | Open |
| --- | --- |
| Browse the public static site | [Battery Evidence Lab](https://rua-creeper-233.github.io/battery-evidence-lab/) |
| Run the local site | [Startup](#startup) |
| Configure optional retrieval-augmented generation | [RAG setup](RAG_SETUP.md) |
| Share a temporary local backend | [Sharing guide](SHARING_GUIDE.md) |
| Read the current generated counts and hashes | [Project status](guides/PROJECT_STATUS.md) |
| Connect an adapter or local model | [Fine-tuning integration](FINETUNE_INTEGRATION.md) |

## What is included

- Static learning pages for materials science, DFT, VASP, MD, and related workflows.
- A curated paper catalogue with DOI, author, year, method, system, and source metadata.
- Search by Chinese question or tags such as `tag:DFT`, `tag:MD`, `tag:VASP`, `tag:MS`, and `type:方法论文`.
- Static rule-based answers and research knowledge cards, with links to sources and stated limits.
- Optional local full-text retrieval and a constrained agent workflow. These require the local backend and locally available PDFs.
- Optional OpenAI-compatible language-model access. The model endpoint is not required for static browsing or deterministic local workflows.
- Optional QLoRA training for organizing research answers, citations, and evidence limits. QLoRA is separate from retrieval and from MLIP training; after generating a reviewed dataset, train and evaluate a local adapter before drawing conclusions about model quality.

The public site is a static browser experience. It cannot run Python, read your local PDFs, access Zotero, or call a local model by itself. The local backend adds retrieval, uploads, keyword extraction, and optional model calls. See the [RAG setup](RAG_SETUP.md) and [sharing guide](SHARING_GUIDE.md) for the boundary.

![Local-data boundary: public assets may be published, while PDFs, private metadata, credentials, and weights remain in local storage.](static/assets/docs/local-data-boundary.svg)

## Current status

Generated counts, dataset hashes, and validation dates are maintained in [PROJECT_STATUS.md](guides/PROJECT_STATUS.md). Historical release notes remain available from the [guides directory](guides/). The status file, not this overview, is the source of current inventory numbers.

## Startup

On Windows, double-click `start.bat`, or run this from the repository root:

```powershell
.\start.ps1
```

Open `http://127.0.0.1:8765`. `start-rag.bat` starts the optional model-backed workflow. `start-share.bat` starts a temporary HTTPS sharing flow. The public GitHub Pages site remains independently browseable.

## Data and evidence maintenance

`data/papers.json` is the public curated bibliography. It contains bibliographic and method metadata, not private acquisition records. Full-text downloads, local manifests, and Zotero deep links remain in ignored or local-only paths.

Typical maintenance commands are:

```powershell
python fetch_literature.py --try-publisher
python audit_library.py
python extract_method_evidence.py
python build_paper_tags.py
```

The downloader uses sources available to the operator and validates PDF identity, title, body or supplement, page count, and SHA-256 where possible. Failed items retain their DOI entry. Automated method signals help locate evidence; calculation parameters still require checking against the target system and the original paper. See [full-text audit](FULLTEXT_AUDIT.md), [method evidence audit](METHOD_EVIDENCE_AUDIT.md), and [paper audit](PAPER_AUDIT.md).

To import existing bibliography records into local Zotero:

```powershell
python import_zotero_library.py --apply
python sync_zotero_links.py
```

## QLoRA and model boundaries

The QLoRA dataset tools create separated train, validation, and test files from selected metadata and authored summaries:

```powershell
python training/expand_dataset.py --insights data/paper_insights.json
python training/validate_dataset.py --train finetune/data/train.jsonl --eval finetune/data/validation.jsonl --test finetune/data/test.jsonl
```

This project keeps its generated train, validation, test and provenance payloads local. Reviewed public data releases would require a separate source-rights and evaluation review. Public releases may contain generators, schemas, and independently authored examples that do not expose that material. `finetune/data/manifest.json` records the local dataset counts, sources, and hashes. New data does not mean that a model has been retrained.

QLoRA targets research-answer organization, citation use, and responses when evidence is insufficient. MLIP training targets energies, forces, and stresses for atomistic simulation. They have different labels, validation criteria, and failure modes. See [fine-tuning integration](FINETUNE_INTEGRATION.md) and the [RTX 3060 guide](training/README_RTX3060.md).

## Stable API surface

| Endpoint | Purpose |
| --- | --- |
| `GET /api/capabilities` | Upload limits, service capabilities, and keyword features |
| `POST /api/chat` | Retrieval-backed answer with optional RAG |
| `POST /api/agent` | Restricted tool-selection workflow |
| `POST /api/upload` | Upload and index a PDF in the local or authorized sharing scope |
| `POST /api/keywords` | Versioned keyword extraction |
| `GET /api/paper-tags` | Tags and per-paper method evidence |
| `GET /api/zotero-links` | Local-only private-library deep links |

Uploaded papers stay in the local private library. Remote requests use a temporary key and restricted Origin when sharing is enabled. Do not publish VASP sources, licenses, POTCAR files, institution sessions, API keys, Zotero private keys, model weights, or local download manifests.

## Validation and release checks

```powershell
python -m unittest discover -s tests
$tests = Get-ChildItem tests/test_*.mjs | ForEach-Object { $_.FullName }
node --test $tests
python validate_research_knowledge.py data/research_knowledge.json
python validate_battery_components.py
python build_static_qa.py
python update_project_status.py --date 2026-10-21
python build_pages.py
python publication_safety.py --public-bundle
python publication_safety.py --staged
python history_safety.py --no-baseline
```

GitHub Actions checks `main` and deploys the generated `docs/` site. Before publishing, run the public-bundle, staged-snapshot, and history checks. Enable the local push hooks after cloning:

```powershell
git config core.hooksPath .githooks
```

See [AGENTS.md](AGENTS.md) for the repository publication rules.

