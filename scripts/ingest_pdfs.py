import argparse
from pathlib import Path

from sqlalchemy import delete

from app.database import SessionLocal, initialize_database
from app.database import KnowledgeChunk
from app.services import KnowledgeService
from app.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest PDF knowledge-base files into PostgreSQL/pgvector.")
    parser.add_argument("directory", type=Path, help="Directory containing synthetic PDF documents")
    parser.add_argument("--replace", action="store_true", help="Replace existing chunks for the supplied document names before ingesting.")
    args = parser.parse_args()
    pdfs = sorted(args.directory.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs found in {args.directory}")
    initialize_database()
    with SessionLocal() as session:
        if args.replace:
            session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_title.in_([pdf.name for pdf in pdfs])))
            session.commit()
        service = KnowledgeService(get_settings())
        total = sum(service.ingest_pdf(session, pdf) for pdf in pdfs)
    print(f"Ingested {total} chunks from {len(pdfs)} PDF files.")


if __name__ == "__main__":
    main()
