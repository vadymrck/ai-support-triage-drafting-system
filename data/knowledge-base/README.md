# Synthetic PDF Knowledge Base

This folder ships with the project’s synthetic PDF knowledge base. The files are intentionally fictional and safe to publish.

They demonstrate PDF parsing, page-aware source metadata, semantic retrieval, and safety-aware routing:

- `SSO Access Guide.pdf`
- `Billing and Invoice Guide.pdf`
- `Data Privacy Requests.pdf`

Each guide has two pages and distinguishes routine first-line support from restricted actions and escalation conditions.

The PDFs are committed as demo fixtures. Do not commit the generated PostgreSQL database or embeddings. After starting Docker, create local vectors from these files with:

```zsh
docker compose exec api python scripts/ingest_pdfs.py data/knowledge-base --replace
```

Use `--replace` after updating a PDF to remove prior chunks for that document name before re-ingesting it.
