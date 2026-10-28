# Local question-answering model data

Updated 2026-10-28. The current generator, `expand_dataset.py`, creates train, validation, and test data from structured paper records and optional curated paper-insight cards. Counts, sources, hashes, and format version are recorded in `training/expanded_manifest.json`, `finetune/data/manifest.json`, and [project status](../guides/PROJECT_STATUS.md). The former two-way dataset remains historical regression material and must not be mixed with the current training or test split.

This is a reviewable data layer for a personal computer. It does not put paper full text into the model. The generator reads structured fields from `data/papers.json`, `data/answer_guidance.json`, `data/answer_regression.json`, and `data/search_training.json`; it does not read PDFs or `fulltext_chunks.jsonl`.

## Generate and validate

Run these commands from the repository root:

```powershell
python training/expand_dataset.py --insights data/paper_insights.json
python training/validate_dataset.py --train finetune/data/train.jsonl --eval finetune/data/validation.jsonl --test finetune/data/test.jsonl
```

The optional `--insights data/paper_insights.json` input supplies curated, structured paper-insight cards. The generator uses their recorded sections and evidence references, preserves the DOI, and labels `reading_guide` entries as workflow guidance rather than reported findings. It does not copy PDF or full-text passages.

Rows are assigned by connected DOI/source-paper groups using SHA-256, with target proportions of about 80/10/10. Actual proportions can vary because whole groups are assigned together. A paper and its comparison questions cannot cross splits. Rows include `messages`, `provenance`, DOI or URL, task category, citation requirements, and `split`. Citation questions include structured evidence packets and `[P1]` identifiers. The validator checks sources, DOI values, duplicate answers, and citation mappings.

The generated files are `expanded_train.jsonl`, `expanded_eval.jsonl`, and `expanded_test.jsonl`, with synchronized copies under `finetune/data/`. The four question families are factual Q&A (`qa_factual.jsonl`), reproduction and workflow (`qa_workflow.jsonl`), refusal and boundary judgments (`qa_refusal.jsonl`), and retrieval-validation tool traces (`tool_traces.jsonl`). Answers use structured fields; when no page number is available, the generator does not invent one.

## Publication and provenance policy

The real train, validation, and test payloads remain local because their rows can carry provenance and source-group information that requires a rights and release review. Keep the corresponding source-group manifests, split manifests, and local provenance records with the local data. This policy also prevents blind test contamination and preserves the ability to audit which DOI-connected records were assigned together.

This does not mean that every training dataset is inherently unpublishable. After explicit review, the repository may publish the generator, schema, aggregate status, and independently authored examples that do not expose restricted rows, private provenance, access records, or unpublished material. Public code and examples must still be checked against the repository publication rules.

## Building a local QLoRA model

Start with RAG before fine-tuning. A local vector store can index paper titles, abstracts, authored evidence, and permitted notes. Retrieve relevant material for each question, then ask a small model to answer with DOI or source references. Updating the index then does not require retraining. `tool_traces.jsonl` can test the retrieval-validation workflow; it is not a record of real tool execution.

With 8–12 GB of VRAM, a 1B–3B instruction model may be practical for LoRA or QLoRA experiments on reviewed `qa_*.jsonl` data. With 16–24 GB, 3B–7B 4-bit QLoRA may be more practical. Before using Transformers, PEFT, TRL, bitsandbytes, or equivalent tools, fix the model license, versions, and random seed. The training data teaches answer structure, citation behavior, and refusal boundaries. It is not a permanent replacement for the evidence store; factual updates should continue through RAG.

If no suitable GPU is available, run RAG or a small CPU evaluation. Do not treat local training capacity as evidence of model quality.

## Minimum evaluation checklist

1. Fit only on `finetune/data/train.jsonl`; use validation data for development choices and hold the test data until the approach is fixed.
2. Check DOI citation, refusal of unsupported questions, and the boundaries between DFT, MD, and force fields.
3. Record exact match or keyword hit rate, citation accuracy, refusal accuracy, and human-sample results. Training loss alone is insufficient.
4. Save the manifest, model version, evaluation results, and error samples for every data or prompt change.
5. Treat a newly generated split as a new version. Do not infer valid accuracy for an older model from the new split, and do not combine the new split with an older model evaluation without rerunning that evaluation.

## Privacy and security

Generation runs locally by default. Do not upload Zotero databases, institutional login information, API keys, private PDFs, or unauthorized full text to a training service or GitHub. Before publishing any dataset, review the exact rows and retain only material that is publicly usable, such as public DOI metadata, publisher URLs, authored short summaries, and approved evidence links.

Keep real train, validation, and test files, source-group manifests, and provenance records local unless an explicit rights and provenance review approves a release. Public generators, schemas, and independently authored examples remain possible after that review. A new split is versioned data, not evidence that a model was trained or that its accuracy improved.

