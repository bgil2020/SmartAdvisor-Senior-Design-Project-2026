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
from backend.rag.operational_storage import (
    default_operational_root,
    inspect_operational_storage,
    publish_candidates,
    recover_last_good,
)
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
    operational_import = sub.add_parser(
        "operational-import",
        help="Atomically publish validated candidates as one operational generation",
    )
    operational_import.add_argument("--course-batch", action="append", type=Path, default=[])
    operational_import.add_argument("--syllabus-batch", action="append", type=Path, default=[])
    operational_import.add_argument("--root", type=Path, default=default_operational_root(ROOT))
    operational_inspect = sub.add_parser(
        "operational-inspect",
        help="Inspect the committed operational generation without source text",
    )
    operational_inspect.add_argument("--root", type=Path, default=default_operational_root(ROOT))
    operational_recover = sub.add_parser(
        "operational-recover",
        help="Validate and explicitly recommit the last-good operational generation",
    )
    operational_recover.add_argument("--root", type=Path, default=default_operational_root(ROOT))
    inspect = sub.add_parser("inspect", help="Show local corpus coverage without source text")
    inspect.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ask = sub.add_parser("ask", help="Run the same retrieval/answer path used by the API")
    ask.add_argument("question")
    ask.add_argument("--course", action="append", default=[])
    ask.add_argument("--term")
    ask.add_argument("--section")
    ask.add_argument(
        "--corpus",
        type=Path,
        help="Explicit legacy corpus override; otherwise operational/environment precedence applies",
    )
    args = parser.parse_args()

    if args.command == "import":
        if not args.course_batch and not args.syllabus_batch:
            parser.error("import requires at least one source batch")
        show(import_validated_corpus(course_batches=args.course_batch, syllabus_batches=args.syllabus_batch, output_path=args.output))
    elif args.command == "operational-import":
        if not args.course_batch and not args.syllabus_batch:
            parser.error("operational-import requires at least one source batch")
        result = publish_candidates(
            args.root,
            course_batches=args.course_batch,
            syllabus_batches=args.syllabus_batch,
        )
        show({
            "changed": result.changed,
            "generation_id": result.generation_id,
            "accepted_record_count": result.accepted_record_count,
            "document_count": result.document_count,
            "chunk_count": result.chunk_count,
            "accepted_sha256": result.accepted_sha256,
            "corpus_sha256": result.corpus_sha256,
            "manifest_path": result.manifest_path,
            "runtime_note": "A separately running API keeps its coherent in-memory generation until restart; in-process publication swaps after validation.",
        })
    elif args.command == "operational-inspect":
        show(inspect_operational_storage(args.root))
    elif args.command == "operational-recover":
        show(recover_last_good(args.root))
    elif args.command == "inspect":
        corpus = load_corpus(args.corpus)
        show({key: corpus[key] for key in ("corpus_version", "created_at", "inputs", "document_count", "chunk_count", "course_coverage", "syllabus_coverage")})
    else:
        result = answer_information_question(args.question, course_codes=args.course, term_id=args.term, section=args.section, corpus_path=args.corpus)
        show(result.model_dump(exclude={"retrieved_evidence"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
