"""
Advanced Chunking Module
Implements token-based, semantic, and hierarchical chunking strategies
"""
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

import tiktoken

from services.document_parser import ParsedSection

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """Represents a document chunk"""
    chunk_id: str
    text: str
    doc_id: str
    doc_name: str
    page_number: int
    chunk_index: int
    doc_type: str  # text, table, image, title
    position: Dict[str, float]
    metadata: Dict[str, Any]
    parent_chunk_id: Optional[str] = None
    image_id: Optional[str] = None


class ChunkingStrategy:
    """Base chunking strategy"""
    
    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except:
            self.tokenizer = None
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        else:
            # Fallback: approximate with words
            return len(text.split())
    
    def chunk_sections(
        self, 
        sections: List[ParsedSection],
        doc_id: str,
        doc_name: str
    ) -> List[Chunk]:
        """Chunk document sections - to be implemented by subclasses"""
        raise NotImplementedError


class TokenChunker(ChunkingStrategy):
    """Token-based chunking with overlap"""
    
    def __init__(
        self, 
        chunk_size: int = 512, 
        overlap: int = 50,
        respect_boundaries: bool = True
    ):
        super().__init__(chunk_size, overlap)
        self.respect_boundaries = respect_boundaries
    
    def chunk_sections(
        self, 
        sections: List[ParsedSection],
        doc_id: str,
        doc_name: str
    ) -> List[Chunk]:
        """Chunk sections using token-based strategy"""
        chunks = []
        chunk_index = 0
        
        for section in sections:
            # Handle non-text sections (tables, images) separately
            if section.doc_type in ['table', 'image']:
                chunks.append(Chunk(
                    chunk_id=f"{doc_id}_chunk_{chunk_index}",
                    text=section.text,
                    doc_id=doc_id,
                    doc_name=doc_name,
                    page_number=section.page_number,
                    chunk_index=chunk_index,
                    doc_type=section.doc_type,
                    position=section.position,
                    metadata=section.metadata,
                    image_id=section.image_id
                ))
                chunk_index += 1
                continue
            
            # Chunk text sections
            text_chunks = self._chunk_text(section.text)
            
            for text_chunk in text_chunks:
                chunks.append(Chunk(
                    chunk_id=f"{doc_id}_chunk_{chunk_index}",
                    text=text_chunk,
                    doc_id=doc_id,
                    doc_name=doc_name,
                    page_number=section.page_number,
                    chunk_index=chunk_index,
                    doc_type=section.doc_type,
                    position=section.position,
                    metadata=section.metadata
                ))
                chunk_index += 1
        
        return chunks
    
    def _chunk_text(self, text: str) -> List[str]:
        """Split text into token-sized chunks with overlap"""
        if not text.strip():
            return []
        
        if self.respect_boundaries:
            # Split by sentences first
            sentences = self._split_sentences(text)
            return self._merge_sentences(sentences)
        else:
            # Simple token-based splitting
            return self._split_by_tokens(text)
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Handle multiple sentence delimiters
        pattern = r'([.!?]+[\s\n]+|[\n]{2,})'
        sentences = re.split(pattern, text)
        
        # Rejoin sentences with their delimiters
        result = []
        i = 0
        while i < len(sentences):
            if i + 1 < len(sentences) and re.match(pattern, sentences[i + 1]):
                result.append(sentences[i] + sentences[i + 1])
                i += 2
            else:
                if sentences[i].strip():
                    result.append(sentences[i])
                i += 1
        
        return [s.strip() for s in result if s.strip()]
    
    def _merge_sentences(self, sentences: List[str]) -> List[str]:
        """Merge sentences into chunks respecting token limits"""
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)
            
            # If single sentence exceeds chunk size, split it
            if sentence_tokens > self.chunk_size:
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                    current_chunk = []
                    current_tokens = 0
                
                # Split long sentence
                sub_chunks = self._split_by_tokens(sentence)
                chunks.extend(sub_chunks)
                continue
            
            # Check if adding sentence would exceed limit
            if current_tokens + sentence_tokens > self.chunk_size:
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                
                # Start new chunk with overlap
                if self.overlap > 0 and current_chunk:
                    overlap_text = self._get_overlap_text(current_chunk)
                    current_chunk = [overlap_text, sentence]
                    current_tokens = self.count_tokens(' '.join(current_chunk))
                else:
                    current_chunk = [sentence]
                    current_tokens = sentence_tokens
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens
        
        # Add remaining chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def _get_overlap_text(self, sentences: List[str]) -> str:
        """Get overlap text from previous chunk"""
        overlap_tokens = 0
        overlap_sentences = []
        
        for sentence in reversed(sentences):
            sentence_tokens = self.count_tokens(sentence)
            if overlap_tokens + sentence_tokens > self.overlap:
                break
            overlap_sentences.insert(0, sentence)
            overlap_tokens += sentence_tokens
        
        return ' '.join(overlap_sentences)
    
    def _split_by_tokens(self, text: str) -> List[str]:
        """Split text by tokens without respecting boundaries"""
        if self.tokenizer:
            tokens = self.tokenizer.encode(text)
            chunks = []
            
            for i in range(0, len(tokens), self.chunk_size - self.overlap):
                chunk_tokens = tokens[i:i + self.chunk_size]
                chunk_text = self.tokenizer.decode(chunk_tokens)
                chunks.append(chunk_text)
            
            return chunks
        else:
            # Fallback: split by words
            words = text.split()
            chunks = []
            
            for i in range(0, len(words), self.chunk_size - self.overlap):
                chunk_words = words[i:i + self.chunk_size]
                chunks.append(' '.join(chunk_words))
            
            return chunks


class SemanticChunker(ChunkingStrategy):
    """Semantic chunking that groups related content"""
    
    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        super().__init__(chunk_size, overlap)
    
    def chunk_sections(
        self, 
        sections: List[ParsedSection],
        doc_id: str,
        doc_name: str
    ) -> List[Chunk]:
        """Chunk sections semantically"""
        chunks = []
        chunk_index = 0
        
        # Group sections by semantic similarity
        grouped_sections = self._group_sections(sections)
        
        for group in grouped_sections:
            # Merge group text
            text = '\n\n'.join([s.text for s in group])
            
            # Get average page number and position
            avg_page = int(sum(s.page_number for s in group) / len(group))
            first_pos = group[0].position
            
            # Check if group fits in chunk size
            if self.count_tokens(text) <= self.chunk_size:
                chunks.append(Chunk(
                    chunk_id=f"{doc_id}_chunk_{chunk_index}",
                    text=text,
                    doc_id=doc_id,
                    doc_name=doc_name,
                    page_number=avg_page,
                    chunk_index=chunk_index,
                    doc_type=group[0].doc_type,
                    position=first_pos,
                    metadata={"section_count": len(group)}
                ))
                chunk_index += 1
            else:
                # Split large groups
                token_chunker = TokenChunker(self.chunk_size, self.overlap)
                sub_chunks = token_chunker.chunk_sections(group, doc_id, doc_name)
                
                for sub_chunk in sub_chunks:
                    sub_chunk.chunk_id = f"{doc_id}_chunk_{chunk_index}"
                    sub_chunk.chunk_index = chunk_index
                    chunks.append(sub_chunk)
                    chunk_index += 1
        
        return chunks
    
    def _group_sections(self, sections: List[ParsedSection]) -> List[List[ParsedSection]]:
        """Group sections by type and proximity"""
        groups = []
        current_group = []
        prev_type = None
        
        for section in sections:
            # Start new group if type changes or it's a special type
            if section.doc_type != prev_type or section.doc_type in ['table', 'image', 'title']:
                if current_group:
                    groups.append(current_group)
                current_group = [section]
                prev_type = section.doc_type
            else:
                current_group.append(section)
        
        if current_group:
            groups.append(current_group)
        
        return groups


class HierarchicalChunker(ChunkingStrategy):
    """Hierarchical chunking with parent-child relationships"""
    
    def __init__(
        self, 
        parent_chunk_size: int = 1024,
        child_chunk_size: int = 256,
        overlap: int = 50
    ):
        super().__init__(child_chunk_size, overlap)
        self.parent_chunk_size = parent_chunk_size
        self.child_chunk_size = child_chunk_size
    
    def chunk_sections(
        self, 
        sections: List[ParsedSection],
        doc_id: str,
        doc_name: str
    ) -> List[Chunk]:
        """Create hierarchical chunks"""
        # First create parent chunks
        parent_chunker = TokenChunker(self.parent_chunk_size, self.overlap)
        parent_chunks = parent_chunker.chunk_sections(sections, doc_id, doc_name)
        
        # Then create child chunks for each parent
        all_chunks = []
        chunk_index = 0
        
        for parent in parent_chunks:
            # Add parent chunk
            parent.chunk_id = f"{doc_id}_parent_{chunk_index}"
            all_chunks.append(parent)
            parent_id = parent.chunk_id
            
            # Create child chunks
            child_chunker = TokenChunker(self.child_chunk_size, self.overlap)
            child_texts = child_chunker._chunk_text(parent.text)
            
            for child_idx, child_text in enumerate(child_texts):
                child_chunk = Chunk(
                    chunk_id=f"{doc_id}_child_{chunk_index}_{child_idx}",
                    text=child_text,
                    doc_id=doc_id,
                    doc_name=doc_name,
                    page_number=parent.page_number,
                    chunk_index=chunk_index,
                    doc_type=parent.doc_type,
                    position=parent.position,
                    metadata=parent.metadata,
                    parent_chunk_id=parent_id
                )
                all_chunks.append(child_chunk)
            
            chunk_index += 1
        
        return all_chunks


def get_chunker(
    strategy: str = "token",
    chunk_size: int = 512,
    overlap: int = 50
) -> ChunkingStrategy:
    """Factory function to get chunker by strategy"""
    
    strategies = {
        "token": lambda: TokenChunker(chunk_size, overlap),
        "semantic": lambda: SemanticChunker(chunk_size, overlap),
        "hierarchical": lambda: HierarchicalChunker(
            parent_chunk_size=chunk_size * 2,
            child_chunk_size=chunk_size,
            overlap=overlap
        )
    }
    
    chunker = strategies.get(strategy)
    if not chunker:
        raise ValueError(f"Unknown chunking strategy: {strategy}")
    
    return chunker()
