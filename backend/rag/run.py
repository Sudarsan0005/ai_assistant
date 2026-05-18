#!/usr/bin/env python
"""
Run the RAG application.
"""
import argparse
from pathlib import Path
import sys

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def run_server():
    """Start the FastAPI server."""
    import uvicorn

    from app.config import settings

    print("=" * 60)
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print("=" * 60)
    print(f"\nAPI: http://localhost:8000")
    print(f"Docs: http://localhost:8000/docs")
    print(f"Vector store: Qdrant at {settings.QDRANT_URL}")
    print(f"LLM provider: {settings.LLM_PROVIDER}\n")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )


def initialize_qdrant():
    """Create the configured Qdrant collection."""
    from services.embedding_service import EmbeddingService
    from services.vector_store import QdrantVectorStore
    from app.config import settings

    embedding_service = EmbeddingService(
        model_name=settings.EMBEDDING_MODEL,
        batch_size=settings.EMBEDDING_BATCH_SIZE,
    )
    store = QdrantVectorStore(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
        collection_name=settings.QDRANT_COLLECTION_NAME,
        dim=embedding_service.get_dimension(),
        prefer_grpc=settings.QDRANT_PREFER_GRPC,
    )
    store.close()
    print(f"Initialized Qdrant collection: {settings.QDRANT_COLLECTION_NAME}")


def run_tests():
    """Run the test suite."""
    import subprocess

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v"],
        cwd=project_root,
    )
    sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(description="RAG Application Runner")
    parser.add_argument("--init", action="store_true", help="Initialize Qdrant collection")
    parser.add_argument("--test", action="store_true", help="Run tests")
    args = parser.parse_args()

    if args.init:
        initialize_qdrant()
    elif args.test:
        run_tests()
    else:
        run_server()


if __name__ == "__main__":
    main()
