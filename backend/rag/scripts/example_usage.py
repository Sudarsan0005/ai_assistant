"""
Example Usage of RAG Pipeline

This script demonstrates:
1. Initializing the RAG pipeline
2. Ingesting documents
3. Querying with citations
4. Managing documents
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from core.rag_pipeline import RAGPipeline
from app.config import settings


def example_basic_usage():
    """Basic RAG pipeline usage"""
    print("=" * 60)
    print("Basic RAG Pipeline Usage Example")
    print("=" * 60)
    
    # Initialize pipeline
    print("\n1. Initializing RAG Pipeline...")
    pipeline = RAGPipeline(
        milvus_host="localhost",
        milvus_port=19530,
        embedding_model="BAAI/bge-base-en-v1.5",
        llm_provider="openai",
        llm_model="gpt-4"
    )
    print("✓ Pipeline initialized")
    
    # Ingest a document
    print("\n2. Ingesting document...")
    doc_metadata = pipeline.ingest_document(
        file_path="./sample_docs/example.pdf",
        filename="example.pdf",
        chunking_strategy="token"
    )
    print(f"✓ Document ingested: {doc_metadata.doc_id}")
    print(f"  - Total chunks: {doc_metadata.total_chunks}")
    print(f"  - Status: {doc_metadata.status}")
    
    # Query the system
    print("\n3. Querying the system...")
    response = pipeline.query(
        question="What is the main topic of this document?",
        use_citations=True
    )
    
    print(f"\n{'='*60}")
    print("QUERY RESULTS")
    print(f"{'='*60}")
    print(f"\nQuery: {response.query}")
    print(f"\nAnswer:\n{response.answer}")
    print(f"\nAnswer with Citations:\n{response.answer_with_citations}")
    print(f"\n{response.references}")
    print(f"\nMetadata:")
    print(f"  - Retrieved chunks: {response.retrieved_chunks}")
    print(f"  - Model used: {response.model_used}")
    print(f"  - Tokens used: {response.tokens_used}")
    
    # Clean up
    print("\n4. Closing pipeline...")
    pipeline.close()
    print("✓ Done")


def example_multi_document():
    """Query across multiple documents"""
    print("=" * 60)
    print("Multi-Document Query Example")
    print("=" * 60)
    
    pipeline = RAGPipeline()
    
    # Ingest multiple documents
    print("\n1. Ingesting multiple documents...")
    docs = []
    
    for file_path in ["doc1.pdf", "doc2.pdf", "doc3.pdf"]:
        try:
            doc_metadata = pipeline.ingest_document(
                file_path=f"./sample_docs/{file_path}",
                filename=file_path,
                chunking_strategy="semantic"
            )
            docs.append(doc_metadata)
            print(f"✓ Ingested: {file_path} ({doc_metadata.total_chunks} chunks)")
        except Exception as e:
            print(f"✗ Failed to ingest {file_path}: {e}")
    
    # Query across all documents
    print("\n2. Querying across all documents...")
    response = pipeline.query(
        question="What are the common themes across these documents?",
        doc_ids=None,  # Query all documents
        use_citations=True
    )
    
    print(f"\nAnswer with Citations:\n{response.answer_with_citations}")
    print(f"\n{response.references}")
    
    # Query specific documents
    if len(docs) >= 2:
        print("\n3. Querying specific documents...")
        response = pipeline.query(
            question="Compare the findings in these documents",
            doc_ids=[docs[0].doc_id, docs[1].doc_id],
            use_citations=True
        )
        
        print(f"\nAnswer:\n{response.answer_with_citations}")
    
    pipeline.close()


def example_chunking_strategies():
    """Compare different chunking strategies"""
    print("=" * 60)
    print("Chunking Strategies Comparison")
    print("=" * 60)
    
    pipeline = RAGPipeline()
    
    file_path = "./sample_docs/example.pdf"
    strategies = ["token", "semantic", "hierarchical"]
    
    for strategy in strategies:
        print(f"\n{'='*40}")
        print(f"Strategy: {strategy}")
        print(f"{'='*40}")
        
        try:
            doc_metadata = pipeline.ingest_document(
                file_path=file_path,
                filename=f"example_{strategy}.pdf",
                chunking_strategy=strategy
            )
            
            print(f"✓ Total chunks: {doc_metadata.total_chunks}")
            
            # Get chunks to analyze
            chunks = pipeline.get_document_chunks(doc_metadata.doc_id)
            
            if chunks:
                avg_length = sum(len(c.get("text", "")) for c in chunks) / len(chunks)
                print(f"  - Average chunk length: {avg_length:.0f} characters")
            
            # Clean up
            pipeline.delete_document(doc_metadata.doc_id)
            
        except Exception as e:
            print(f"✗ Failed: {e}")
    
    pipeline.close()


def example_vision_processing():
    """Process documents with vision capabilities"""
    print("=" * 60)
    print("Vision-Based Document Processing")
    print("=" * 60)
    
    pipeline = RAGPipeline(enable_vision=True)
    
    # Ingest image or PDF with images
    print("\n1. Ingesting document with images...")
    
    image_files = ["diagram.png", "scanned_document.pdf", "table_image.jpg"]
    
    for image_file in image_files:
        try:
            doc_metadata = pipeline.ingest_document(
                file_path=f"./sample_docs/{image_file}",
                filename=image_file,
                chunking_strategy="token"
            )
            
            print(f"✓ Processed: {image_file}")
            print(f"  - Chunks created: {doc_metadata.total_chunks}")
            
            # Query about image content
            response = pipeline.query(
                question="What information is shown in the images?",
                doc_ids=[doc_metadata.doc_id],
                use_citations=True
            )
            
            print(f"\nExtracted information:\n{response.answer}")
            
        except Exception as e:
            print(f"✗ Failed to process {image_file}: {e}")
    
    pipeline.close()


def example_citation_management():
    """Demonstrate citation management features"""
    print("=" * 60)
    print("Citation Management Example")
    print("=" * 60)
    
    pipeline = RAGPipeline()
    
    # Ingest document
    print("\n1. Ingesting document...")
    doc_metadata = pipeline.ingest_document(
        file_path="./sample_docs/research_paper.pdf",
        filename="research_paper.pdf"
    )
    
    # Query with different citation settings
    print("\n2. Testing citation insertion...")
    
    # With citations
    print("\n--- WITH CITATIONS ---")
    response_with = pipeline.query(
        question="What are the key findings?",
        use_citations=True
    )
    print(response_with.answer_with_citations)
    print(f"\nTotal citations: {len(response_with.citations)}")
    
    # Without citations
    print("\n--- WITHOUT CITATIONS ---")
    response_without = pipeline.query(
        question="What are the key findings?",
        use_citations=False
    )
    print(response_without.answer)
    
    # Show citation details
    print("\n3. Citation details:")
    for citation in response_with.citations[:5]:  # Show first 5
        print(f"\n[{citation['citation_id']}]")
        print(f"  Document: {citation['doc_name']}")
        print(f"  Page: {citation['page_number']}")
        print(f"  Similarity: {citation['similarity']:.2f}")
    
    pipeline.close()


def example_document_management():
    """Demonstrate document management"""
    print("=" * 60)
    print("Document Management Example")
    print("=" * 60)
    
    pipeline = RAGPipeline()
    
    # Ingest documents
    print("\n1. Ingesting documents...")
    doc_ids = []
    for i in range(3):
        doc_metadata = pipeline.ingest_document(
            file_path=f"./sample_docs/doc{i}.pdf",
            filename=f"doc{i}.pdf"
        )
        doc_ids.append(doc_metadata.doc_id)
        print(f"✓ Document {i+1} ingested")
    
    # List documents
    print("\n2. Listing documents...")
    documents = pipeline.list_documents()
    for doc in documents:
        print(f"  - {doc.filename} ({doc.total_chunks} chunks)")
    
    # Get specific document info
    print("\n3. Getting document details...")
    doc_info = pipeline.get_document_info(doc_ids[0])
    print(f"  Document ID: {doc_info.doc_id}")
    print(f"  Filename: {doc_info.filename}")
    print(f"  Total chunks: {doc_info.total_chunks}")
    print(f"  Status: {doc_info.status}")
    
    # Get document chunks
    print("\n4. Retrieving chunks...")
    chunks = pipeline.get_document_chunks(doc_ids[0])
    print(f"  Total chunks: {len(chunks)}")
    if chunks:
        print(f"  First chunk preview: {chunks[0].get('text', '')[:100]}...")
    
    # Delete document
    print("\n5. Deleting document...")
    pipeline.delete_document(doc_ids[0])
    print(f"✓ Document deleted")
    
    # Verify deletion
    remaining = pipeline.list_documents()
    print(f"  Remaining documents: {len(remaining)}")
    
    pipeline.close()


if __name__ == "__main__":
    print("RAG Pipeline Examples")
    print("=" * 60)
    print("\nAvailable examples:")
    print("1. Basic usage")
    print("2. Multi-document query")
    print("3. Chunking strategies")
    print("4. Vision processing")
    print("5. Citation management")
    print("6. Document management")
    
    # Run basic example
    try:
        example_basic_usage()
    except Exception as e:
        print(f"\nError: {e}")
        print("\nNote: Make sure to:")
        print("1. Start Milvus: docker-compose up -d")
        print("2. Set API keys in .env file")
        print("3. Place sample documents in ./sample_docs/")
