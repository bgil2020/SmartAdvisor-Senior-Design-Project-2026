"""Build and inspect the local validated RAG v0 corpus."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.rag.corpus import import_validated_corpus, load_corpus
from backend.rag.service import answer_information_question

DEFAULT_CORPUS = ROOT / "data" / "rag" / "local-corpus.json"


def show(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("import", help="Validate source batches and build a local corpus")
    build.add_argument("--course-batch", action="append", type=Path, default=[])
    build.add_argument("--syllabus-batch", action="append", type=Path, default=[])
    build.add_argument("--output", type=Path, default=DEFAULT_CORPUS)
    inspect = sub.add_parser("inspect", help="Show local corpus coverage without source text")
    inspect.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ask = sub.add_parser("ask", help="Run the same retrieval/answer path used by the API")
    ask.add_argument("question")
    ask.add_argument("--course", action="append", default=[])
    ask.add_argument("--term")
    ask.add_argument("--section")
    ask.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    args = parser.parse_args()

    if args.command == "import":
        if not args.course_batch and not args.syllabus_batch:
            parser.error("import requires at least one source batch")
        show(import_validated_corpus(course_batches=args.course_batch, syllabus_batches=args.syllabus_batch, output_path=args.output))
    elif args.command == "inspect":
        corpus = load_corpus(args.corpus)
        show({key: corpus[key] for key in ("corpus_version", "created_at", "inputs", "document_count", "chunk_count", "course_coverage", "syllabus_coverage")})
    else:
        result = answer_information_question(args.question, course_codes=args.course, term_id=args.term, section=args.section, corpus_path=args.corpus)
        show(result.model_dump(exclude={"retrieved_evidence"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
