"""
Simple Test Script for RAG Application

Tests basic functionality without requiring actual documents
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    
    try:
        import app.config
        print("✓ app.config")
        
        import services.document_parser
        print("✓ services.document_parser")
        
        import services.chunking
        print("✓ services.chunking")
        
        import services.embedding_service
        print("✓ services.embedding_service")
        
        import services.vector_store
        print("✓ services.vector_store")
        
        import services.retrieval_service
        print("✓ services.retrieval_service")
        
        import services.llm_service
        print("✓ services.llm_service")
        
        import core.rag_pipeline
        print("✓ core.rag_pipeline")
        
        import app.main
        print("✓ app.main")
        
        print("\n✅ All imports successful!")
        return True
        
    except Exception as e:
        print(f"\n❌ Import failed: {e}")
        return False


def test_chunking():
    """Test chunking strategies"""
    print("\nTesting chunking...")
    
    try:
        from services.chunking import get_chunker
        from services.document_parser import ParsedSection
        
        # Create sample sections
        sections = [
            ParsedSection(
                text="This is a sample text for testing chunking strategies.",
                doc_type="text",
                page_number=1,
                position={"x0": 0, "y0": 0, "x1": 100, "y1": 100},
                metadata={}
            )
        ]
        
        # Test token chunker
        chunker = get_chunker("token", chunk_size=50, overlap=10)
        chunks = chunker.chunk_sections(sections, "test_doc", "test.txt")
        
        print(f"✓ Token chunker created {len(chunks)} chunks")
        
        print("\n✅ Chunking test successful!")
        return True
        
    except Exception as e:
        print(f"\n❌ Chunking test failed: {e}")
        return False


def test_embedding_service():
    """Test embedding service"""
    print("\nTesting embedding service...")
    
    try:
        from services.embedding_service import EmbeddingService
        
        # This will download the model if not present
        print("Initializing embedding service (may take a moment)...")
        service = EmbeddingService(
            model_name="BAAI/bge-small-en-v1.5",  # Smaller model for testing
            device="cpu"
        )
        
        print(f"✓ Model loaded, dimension: {service.get_dimension()}")
        
        # Test encoding
        test_texts = ["Hello world", "This is a test"]
        embeddings = service.encode_texts(test_texts)
        
        print(f"✓ Encoded {len(test_texts)} texts")
        print(f"✓ Embedding shape: {embeddings.shape}")
        
        print("\n✅ Embedding service test successful!")
        return True
        
    except Exception as e:
        print(f"\n❌ Embedding service test failed: {e}")
        print("Note: This requires downloading the embedding model")
        return False


def test_document_parser():
    """Test document parser"""
    print("\nTesting document parser...")
    
    try:
        from services.document_parser import DocumentParser
        
        parser = DocumentParser(enable_vision=False)  # Disable vision for basic test
        print("✓ Document parser initialized")
        
        # Test text parsing
        test_file = Path("test_sample.txt")
        test_file.write_text("This is a test document.\n\nIt has multiple paragraphs.")
        
        sections = parser.parse(str(test_file), "test_sample.txt")
        print(f"✓ Parsed {len(sections)} sections from text file")
        
        # Cleanup
        test_file.unlink()
        
        print("\n✅ Document parser test successful!")
        return True
        
    except Exception as e:
        print(f"\n❌ Document parser test failed: {e}")
        return False


def test_api_client():
    """Test API client (requires running server)"""
    print("\nTesting API client...")
    
    try:
        from utils.api_client import RAGClient
        
        client = RAGClient("http://localhost:8000")
        
        # Try health check
        health = client.health_check()
        print(f"✓ API health check: {health['status']}")
        
        client.close()
        
        print("\n✅ API client test successful!")
        return True
        
    except Exception as e:
        print(f"\n❌ API client test failed: {e}")
        print("Note: This requires the API server to be running")
        return False


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("RAG Application Test Suite")
    print("=" * 60)
    
    results = {
        "Imports": test_imports(),
        "Chunking": test_chunking(),
        "Document Parser": test_document_parser(),
        "Embedding Service": test_embedding_service(),
        "API Client": test_api_client(),
    }
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:20} {status}")
    
    total = len(results)
    passed = sum(results.values())
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        print("\nNote: Some tests may fail if:")
        print("  - Dependencies are not fully installed")
        print("  - Qdrant is not running")
        print("  - API server is not running")
        print("  - API keys are not configured")


if __name__ == "__main__":
    run_all_tests()
