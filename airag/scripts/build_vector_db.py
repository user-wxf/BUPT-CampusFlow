from argparse import ArgumentParser

from airag.embedding import DEFAULT_EMBEDDING_MODEL, FastEmbedTextEmbedder
from airag.retrieval import DEFAULT_CHUNKS_PATH
from airag.vector_store import DEFAULT_VECTOR_DB_PATH, build_vector_db


def main() -> None:
    parser = ArgumentParser(description="Build local vector DB from airag chunks.jsonl")
    parser.add_argument("--chunks", default=str(DEFAULT_CHUNKS_PATH))
    parser.add_argument("--output", default=str(DEFAULT_VECTOR_DB_PATH))
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    args = parser.parse_args()
    result = build_vector_db(args.chunks, args.output, FastEmbedTextEmbedder(args.model))
    print(f"Vector DB built: {result['path']}")
    print(f"Model: {result['model']}")
    print(f"Chunks: {result['chunk_count']}")


if __name__ == "__main__":
    main()
