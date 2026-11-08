# Evidence and privacy policy

Battery Evidence Lab separates public bibliographic evidence from local full text.

## Public tree

The repository and GitHub Pages may contain selected DOI, author, year, method, system, and teaching metadata. Public summaries describe the evidence boundary and reproducible workflow without exposing private acquisition records.

## Local tree

PDFs, extracted text, page-level indexes, Zotero item and attachment keys, access records, signed URLs, credentials, local manifests, model weights, and detailed audit outputs stay in ignored or local-only paths. Use the original PDF as the primary source when checking a paper.

## Review rule

Automated method signals and metadata checks help locate evidence. Before using a parameter, number, or scientific interpretation in research, open the cited page and check the original paper and supplement. A DOI or a valid citation marker does not prove that a claim is correct or that the full text is publicly available.

## Publication boundary

Run `publication_safety.py --public-bundle` and `history_safety.py --no-baseline` before publishing. Public builds must contain sanitized Zotero mappings and empty private evidence payloads. Detailed historical reports are kept in the local review archive rather than the public repository.
