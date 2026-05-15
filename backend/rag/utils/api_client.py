"""
RAG API Client
Easy-to-use client for interacting with the RAG API
"""
import requests
from typing import List, Optional, Dict, Any
from pathlib import Path


class RAGClient:
    """Client for RAG API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health"""
        response = self.session.get(f"{self.base_url}/")
        response.raise_for_status()
        return response.json()
    
    def upload_document(
        self,
        file_path: str,
        chunking_strategy: str = "token"
    ) -> Dict[str, Any]:
        """
        Upload and ingest a document
        
        Args:
            file_path: Path to document file
            chunking_strategy: token, semantic, or hierarchical
        
        Returns:
            Document metadata
        """
        file_path = Path(file_path)
        
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f)}
            params = {'chunking_strategy': chunking_strategy}
            
            response = self.session.post(
                f"{self.base_url}/documents/upload",
                files=files,
                params=params
            )
            response.raise_for_status()
            return response.json()
    
    def query(
        self,
        question: str,
        doc_ids: Optional[List[str]] = None,
        use_citations: bool = True
    ) -> Dict[str, Any]:
        """
        Query the RAG system
        
        Args:
            question: Question to ask
            doc_ids: Optional list of document IDs to search
            use_citations: Whether to include citations
        
        Returns:
            Query response with answer and citations
        """
        payload = {
            "question": question,
            "doc_ids": doc_ids,
            "use_citations": use_citations
        }
        
        response = self.session.post(
            f"{self.base_url}/query",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def list_documents(self) -> List[Dict[str, Any]]:
        """List all documents"""
        response = self.session.get(f"{self.base_url}/documents")
        response.raise_for_status()
        return response.json()
    
    def get_document(self, doc_id: str) -> Dict[str, Any]:
        """Get document information"""
        response = self.session.get(f"{self.base_url}/documents/{doc_id}")
        response.raise_for_status()
        return response.json()
    
    def delete_document(self, doc_id: str) -> Dict[str, Any]:
        """Delete a document"""
        response = self.session.delete(f"{self.base_url}/documents/{doc_id}")
        response.raise_for_status()
        return response.json()
    
    def get_document_chunks(self, doc_id: str) -> Dict[str, Any]:
        """Get all chunks for a document"""
        response = self.session.get(f"{self.base_url}/documents/{doc_id}/chunks")
        response.raise_for_status()
        return response.json()
    
    def close(self):
        """Close the session"""
        self.session.close()


# Example usage
if __name__ == "__main__":
    # Initialize client
    client = RAGClient("http://localhost:8000")
    
    # Check health
    print("Checking API health...")
    health = client.health_check()
    print(f"Status: {health['status']}")
    
    # Upload document
    print("\nUploading document...")
    doc = client.upload_document(
        file_path="./sample_docs/example.pdf",
        chunking_strategy="token"
    )
    print(f"Document uploaded: {doc['doc_id']}")
    print(f"Total chunks: {doc['total_chunks']}")
    
    # Query
    print("\nQuerying...")
    response = client.query(
        question="What is this document about?",
        use_citations=True
    )
    
    print(f"\nAnswer with Citations:")
    print(response['answer_with_citations'])
    print(f"\n{response['references']}")
    
    print(f"\nMetadata:")
    print(f"  Retrieved chunks: {response['retrieved_chunks']}")
    print(f"  Model: {response['model_used']}")
    print(f"  Tokens: {response['tokens_used']}")
    
    # List documents
    print("\nListing documents...")
    documents = client.list_documents()
    for doc in documents:
        print(f"  - {doc['filename']} ({doc['total_chunks']} chunks)")
    
    client.close()
