"""Vector index implementation with FAISS for semantic code search."""

import json
import logging
import pickle
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np

from agent.config import get_settings
from agent.llm.bedrock_client import BedrockClient
from agent.security.sandbox import SecuritySandbox
from agent.vector.chunking import CodeChunker, ChunkResult
from agent.vector.search import SearchResult, SearchRanker

logger = logging.getLogger(__name__)


class VectorIndexError(Exception):
    """Exception for vector index operations."""
    pass


class VectorIndex:
    """Vector index for semantic code search using FAISS."""
    
    def __init__(
        self,
        index_path: Optional[Path] = None,
        bedrock_client: Optional[BedrockClient] = None,
        workspace_root: Optional[str] = None
    ):
        """Initialize vector index.
        
        Args:
            index_path: Path to store index files
            bedrock_client: Bedrock client for embeddings
            workspace_root: Root directory for workspace operations
        """
        settings = get_settings()
        
        # Set up paths
        self.workspace_root = Path(workspace_root or settings.workspace_root).resolve()
        self.index_path = index_path or Path(settings.vector_index_path)
        self.index_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.bedrock = bedrock_client or BedrockClient()
        self.sandbox = SecuritySandbox(self.workspace_root)
        self.chunker = CodeChunker(max_chunk_size=1000, overlap_size=100)
        self.ranker = SearchRanker(snippet_length=200, context_lines=2)
        
        # Index state
        self.faiss_index: Optional[faiss.Index] = None
        self.metadata: Dict[int, Dict[str, Any]] = {}
        self.file_hashes: Dict[str, str] = {}
        self.embedding_dim = 1536  # Titan embedding dimension
        self.next_id = 0
        
        # Load existing index if available
        self._load_index()
        
        logger.info(f"Initialized VectorIndex with workspace: {self.workspace_root}")
        logger.info(f"Index path: {self.index_path}")
    
    def _load_index(self):
        """Load existing FAISS index and metadata."""
        try:
            index_file = self.index_path / "index.faiss"
            metadata_file = self.index_path / "metadata.json"
            hashes_file = self.index_path / "file_hashes.json"
            
            if index_file.exists() and metadata_file.exists():
                # Load FAISS index
                self.faiss_index = faiss.read_index(str(index_file))
                logger.info(f"Loaded FAISS index with {self.faiss_index.ntotal} vectors")
                
                # Load metadata
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata_raw = json.load(f)
                    self.metadata = {int(k): v for k, v in metadata_raw.items()}
                
                # Load file hashes
                if hashes_file.exists():
                    with open(hashes_file, 'r', encoding='utf-8') as f:
                        self.file_hashes = json.load(f)
                
                # Set next ID
                if self.metadata:
                    self.next_id = max(self.metadata.keys()) + 1
                
                logger.info(f"Loaded metadata for {len(self.metadata)} chunks")
                
            else:
                logger.info("No existing index found, will create new one")
                
        except Exception as e:
            logger.error(f"Failed to load existing index: {e}")
            self._initialize_empty_index()
    
    def _initialize_empty_index(self):
        """Initialize empty FAISS index."""
        try:
            # Create FAISS index (using IndexFlatIP for cosine similarity)
            self.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
            self.metadata = {}
            self.file_hashes = {}
            self.next_id = 0
            
            logger.info("Initialized empty FAISS index")
            
        except Exception as e:
            raise VectorIndexError(f"Failed to initialize FAISS index: {e}") from e
    
    def _save_index(self):
        """Save FAISS index and metadata to disk."""
        try:
            if self.faiss_index is None:
                return
            
            # Save FAISS index
            index_file = self.index_path / "index.faiss"
            faiss.write_index(self.faiss_index, str(index_file))
            
            # Save metadata
            metadata_file = self.index_path / "metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2, ensure_ascii=False)
            
            # Save file hashes
            hashes_file = self.index_path / "file_hashes.json"
            with open(hashes_file, 'w', encoding='utf-8') as f:
                json.dump(self.file_hashes, f, indent=2)
            
            logger.info(f"Saved index with {self.faiss_index.ntotal} vectors")
            
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
            raise VectorIndexError(f"Failed to save index: {e}") from e
    
    async def build_index(self, force_rebuild: bool = False) -> Dict[str, Any]:
        """Build vector index for the entire workspace.
        
        Args:
            force_rebuild: Whether to rebuild index even if files haven't changed
            
        Returns:
            Dictionary with build statistics
        """
        start_time = time.time()
        stats = {
            'files_processed': 0,
            'files_skipped': 0,
            'chunks_created': 0,
            'chunks_indexed': 0,
            'errors': [],
            'duration': 0.0,
        }
        
        try:
            logger.info("Starting workspace index build")
            
            # Initialize index if needed
            if self.faiss_index is None:
                self._initialize_empty_index()
            
            # Find all files to index
            files_to_process = []
            for file_path in self.workspace_root.rglob('*'):
                if file_path.is_file() and self.chunker.should_index_file(file_path):
                    files_to_process.append(file_path)
            
            logger.info(f"Found {len(files_to_process)} files to process")
            
            # Process files
            for file_path in files_to_process:
                try:
                    result = await self._process_file(file_path, force_rebuild)
                    if result['processed']:
                        stats['files_processed'] += 1
                        stats['chunks_created'] += result['chunks_created']
                        stats['chunks_indexed'] += result['chunks_indexed']
                    else:
                        stats['files_skipped'] += 1
                        
                except Exception as e:
                    error_msg = f"Error processing {file_path}: {e}"
                    logger.error(error_msg)
                    stats['errors'].append(error_msg)
            
            # Save index
            self._save_index()
            
            stats['duration'] = time.time() - start_time
            
            logger.info(f"Index build completed in {stats['duration']:.2f}s")
            logger.info(f"Processed {stats['files_processed']} files, "
                       f"created {stats['chunks_indexed']} chunks")
            
            return stats
            
        except Exception as e:
            error_msg = f"Failed to build index: {e}"
            logger.error(error_msg)
            stats['errors'].append(error_msg)
            stats['duration'] = time.time() - start_time
            return stats
    
    async def _process_file(self, file_path: Path, force_rebuild: bool = False) -> Dict[str, Any]:
        """Process a single file for indexing.
        
        Args:
            file_path: Path to file to process
            force_rebuild: Whether to force rebuild even if unchanged
            
        Returns:
            Dictionary with processing results
        """
        result = {
            'processed': False,
            'chunks_created': 0,
            'chunks_indexed': 0,
        }
        
        try:
            # Validate path
            validated_path = self.sandbox.validate_path(str(file_path))
            
            # Check if file has changed
            file_hash = self._calculate_file_hash(validated_path)
            relative_path = str(validated_path.relative_to(self.workspace_root))
            
            if not force_rebuild and relative_path in self.file_hashes:
                if self.file_hashes[relative_path] == file_hash:
                    logger.debug(f"Skipping unchanged file: {relative_path}")
                    return result
            
            # Read file content
            try:
                content = validated_path.read_text(encoding='utf-8', errors='ignore')
            except Exception as e:
                logger.warning(f"Could not read file {file_path}: {e}")
                return result
            
            # Skip empty files
            if not content.strip():
                logger.debug(f"Skipping empty file: {relative_path}")
                return result
            
            # Remove existing chunks for this file
            await self._remove_file_chunks(relative_path)
            
            # Chunk the file
            chunks = self.chunker.chunk_file(validated_path, content)
            result['chunks_created'] = len(chunks)
            
            if not chunks:
                return result
            
            # Generate embeddings and add to index
            chunk_texts = [chunk.content for chunk in chunks]
            embeddings = await self._generate_embeddings(chunk_texts)
            
            if embeddings is not None and len(embeddings) > 0:
                await self._add_chunks_to_index(chunks, embeddings, relative_path)
                result['chunks_indexed'] = len(chunks)
                
                # Update file hash
                self.file_hashes[relative_path] = file_hash
                result['processed'] = True
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {e}")
            raise
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate hash of file content and metadata.
        
        Args:
            file_path: Path to file
            
        Returns:
            File hash string
        """
        import hashlib
        
        try:
            # Hash file content and modification time
            content = file_path.read_bytes()
            mtime = file_path.stat().st_mtime
            
            hasher = hashlib.sha256()
            hasher.update(content)
            hasher.update(str(mtime).encode())
            
            return hasher.hexdigest()
            
        except Exception as e:
            logger.warning(f"Could not calculate hash for {file_path}: {e}")
            return ""
    
    async def _remove_file_chunks(self, file_path: str):
        """Remove existing chunks for a file from the index.
        
        Args:
            file_path: Relative path to file
        """
        if self.faiss_index is None:
            return
        
        # Find chunks for this file
        chunks_to_remove = []
        for chunk_id, metadata in self.metadata.items():
            if metadata.get('file_path') == file_path:
                chunks_to_remove.append(chunk_id)
        
        if chunks_to_remove:
            logger.debug(f"Removing {len(chunks_to_remove)} existing chunks for {file_path}")
            
            # Remove from metadata
            for chunk_id in chunks_to_remove:
                del self.metadata[chunk_id]
            
            # Note: FAISS doesn't support efficient removal of specific vectors
            # For now, we'll rebuild the index if there are many removals
            # In production, consider using IndexIDMap for better removal support
    
    async def _generate_embeddings(self, texts: List[str]) -> Optional[np.ndarray]:
        """Generate embeddings for text chunks.
        
        Args:
            texts: List of text chunks
            
        Returns:
            Numpy array of embeddings or None if failed
        """
        try:
            if not texts:
                return None
            
            # Generate embeddings using Bedrock
            embeddings = await self.bedrock.generate_embeddings(texts)
            
            if embeddings is not None and len(embeddings) > 0:
                return np.array(embeddings, dtype=np.float32)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            return None
    
    async def _add_chunks_to_index(
        self,
        chunks: List[ChunkResult],
        embeddings: np.ndarray,
        file_path: str
    ):
        """Add chunks and embeddings to FAISS index.
        
        Args:
            chunks: List of code chunks
            embeddings: Corresponding embeddings
            file_path: Relative file path
        """
        if self.faiss_index is None:
            self._initialize_empty_index()
        
        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)
        
        # Add to FAISS index
        self.faiss_index.add(embeddings)
        
        # Add metadata
        for i, chunk in enumerate(chunks):
            chunk_id = self.next_id + i
            self.metadata[chunk_id] = {
                'file_path': file_path,
                'start_line': chunk.start_line,
                'end_line': chunk.end_line,
                'chunk_type': chunk.chunk_type,
                'language': chunk.language,
                'content': chunk.content,
                'metadata': chunk.metadata,
            }
        
        self.next_id += len(chunks)
        
        logger.debug(f"Added {len(chunks)} chunks to index for {file_path}")
    
    async def search(
        self,
        query: str,
        top_k: int = 20,
        min_score: float = 0.1,
        file_filter: Optional[str] = None,
        language_filter: Optional[str] = None,
        chunk_type_filter: Optional[str] = None
    ) -> List[SearchResult]:
        """Search the vector index.
        
        Args:
            query: Search query
            top_k: Maximum number of results
            min_score: Minimum similarity score
            file_filter: Filter by file path pattern
            language_filter: Filter by programming language
            chunk_type_filter: Filter by chunk type
            
        Returns:
            List of search results
        """
        try:
            if self.faiss_index is None or self.faiss_index.ntotal == 0:
                logger.warning("No index available for search")
                return []
            
            # Generate query embedding
            query_embeddings = await self._generate_embeddings([query])
            if query_embeddings is None or len(query_embeddings) == 0:
                logger.error("Failed to generate query embedding")
                return []
            
            query_vector = query_embeddings[0:1]  # Shape: (1, dim)
            faiss.normalize_L2(query_vector)
            
            # Search FAISS index
            scores, indices = self.faiss_index.search(query_vector, min(top_k * 2, self.faiss_index.ntotal))
            
            # Convert to search results
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx == -1 or score < min_score:
                    continue
                
                if idx not in self.metadata:
                    logger.warning(f"Missing metadata for index {idx}")
                    continue
                
                metadata = self.metadata[idx]
                
                # Apply filters
                if file_filter and file_filter not in metadata['file_path']:
                    continue
                
                if language_filter and metadata['language'] != language_filter:
                    continue
                
                if chunk_type_filter and metadata['chunk_type'] != chunk_type_filter:
                    continue
                
                result = SearchResult(
                    content=metadata['content'],
                    file_path=metadata['file_path'],
                    start_line=metadata['start_line'],
                    end_line=metadata['end_line'],
                    score=float(score),
                    chunk_type=metadata['chunk_type'],
                    language=metadata['language'],
                    metadata=metadata['metadata'],
                )
                
                results.append(result)
            
            # Rank and post-process results
            ranked_results = self.ranker.rank_results(results, query, top_k)
            
            logger.info(f"Search for '{query}' returned {len(ranked_results)} results")
            
            return ranked_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    async def update_file(self, file_path: str) -> Dict[str, Any]:
        """Update index for a specific file.
        
        Args:
            file_path: Path to file to update (relative to workspace)
            
        Returns:
            Dictionary with update results
        """
        try:
            full_path = self.workspace_root / file_path
            validated_path = self.sandbox.validate_path(str(full_path))
            
            if not validated_path.exists():
                # File was deleted, remove from index
                await self._remove_file_chunks(file_path)
                if file_path in self.file_hashes:
                    del self.file_hashes[file_path]
                
                return {
                    'action': 'removed',
                    'file_path': file_path,
                    'chunks_removed': 0,  # We don't track exact count
                }
            
            # Process the file
            result = await self._process_file(validated_path, force_rebuild=True)
            
            # Save index
            self._save_index()
            
            return {
                'action': 'updated',
                'file_path': file_path,
                'processed': result['processed'],
                'chunks_created': result['chunks_created'],
                'chunks_indexed': result['chunks_indexed'],
            }
            
        except Exception as e:
            logger.error(f"Failed to update file {file_path}: {e}")
            return {
                'action': 'error',
                'file_path': file_path,
                'error': str(e),
            }
    
    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector index.
        
        Returns:
            Dictionary with index statistics
        """
        try:
            total_vectors = self.faiss_index.ntotal if self.faiss_index else 0
            
            # Count by language and chunk type
            languages = {}
            chunk_types = {}
            files = set()
            
            for metadata in self.metadata.values():
                lang = metadata['language']
                languages[lang] = languages.get(lang, 0) + 1
                
                chunk_type = metadata['chunk_type']
                chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
                
                files.add(metadata['file_path'])
            
            return {
                'total_vectors': total_vectors,
                'total_chunks': len(self.metadata),
                'total_files': len(files),
                'languages': languages,
                'chunk_types': chunk_types,
                'index_path': str(self.index_path),
                'embedding_dimension': self.embedding_dim,
            }
            
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            return {'error': str(e)}
    
    def clear_index(self):
        """Clear the entire vector index."""
        try:
            self._initialize_empty_index()
            self.file_hashes.clear()
            
            # Remove index files
            for file_path in self.index_path.glob("*"):
                if file_path.is_file():
                    file_path.unlink()
            
            logger.info("Cleared vector index")
            
        except Exception as e:
            logger.error(f"Failed to clear index: {e}")
            raise VectorIndexError(f"Failed to clear index: {e}") from e