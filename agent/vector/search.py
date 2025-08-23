"""Search result handling and ranking for vector search."""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from vector search operation."""
    content: str
    file_path: str
    start_line: int
    end_line: int
    score: float
    chunk_type: str
    language: str
    metadata: Dict[str, Any]
    snippet: Optional[str] = None
    highlighted_snippet: Optional[str] = None
    
    @property
    def line_count(self) -> int:
        """Get number of lines in result."""
        return self.end_line - self.start_line + 1
    
    @property
    def location(self) -> str:
        """Get human-readable location string."""
        return f"{self.file_path}:{self.start_line}-{self.end_line}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'content': self.content,
            'file_path': self.file_path,
            'start_line': self.start_line,
            'end_line': self.end_line,
            'score': self.score,
            'chunk_type': self.chunk_type,
            'language': self.language,
            'metadata': self.metadata,
            'snippet': self.snippet,
            'highlighted_snippet': self.highlighted_snippet,
            'line_count': self.line_count,
            'location': self.location,
        }


class SearchRanker:
    """Rank and post-process search results."""
    
    def __init__(self, snippet_length: int = 200, context_lines: int = 2):
        """Initialize search ranker.
        
        Args:
            snippet_length: Maximum length of extracted snippets
            context_lines: Number of context lines around matches
        """
        self.snippet_length = snippet_length
        self.context_lines = context_lines
    
    def rank_results(
        self,
        results: List[SearchResult],
        query: str,
        max_results: int = 20
    ) -> List[SearchResult]:
        """Rank search results by relevance.
        
        Args:
            results: Raw search results from vector index
            query: Original search query
            max_results: Maximum number of results to return
            
        Returns:
            Ranked and processed search results
        """
        if not results:
            return []
        
        # Apply additional ranking factors
        scored_results = []
        for result in results:
            enhanced_score = self._calculate_enhanced_score(result, query)
            result.score = enhanced_score
            scored_results.append(result)
        
        # Sort by enhanced score
        scored_results.sort(key=lambda x: x.score, reverse=True)
        
        # Take top results
        top_results = scored_results[:max_results]
        
        # Generate snippets and highlights
        for result in top_results:
            result.snippet = self._extract_snippet(result.content, query)
            result.highlighted_snippet = self._highlight_snippet(result.snippet, query)
        
        # Remove duplicates and near-duplicates
        deduplicated = self._deduplicate_results(top_results)
        
        return deduplicated
    
    def _calculate_enhanced_score(self, result: SearchResult, query: str) -> float:
        """Calculate enhanced relevance score.
        
        Args:
            result: Search result to score
            query: Search query
            
        Returns:
            Enhanced relevance score
        """
        base_score = result.score
        
        # Boost factors
        boosts = []
        
        # 1. Exact query matches in content
        query_lower = query.lower()
        content_lower = result.content.lower()
        exact_matches = content_lower.count(query_lower)
        if exact_matches > 0:
            boosts.append(0.3 * min(exact_matches, 3))  # Cap at 3 matches
        
        # 2. Query words in content
        query_words = set(re.findall(r'\w+', query_lower))
        content_words = set(re.findall(r'\w+', content_lower))
        word_overlap = len(query_words.intersection(content_words))
        if query_words:
            word_ratio = word_overlap / len(query_words)
            boosts.append(0.2 * word_ratio)
        
        # 3. Chunk type preferences
        type_boosts = {
            'function': 0.15,
            'class': 0.15,
            'method': 0.1,
            'import': 0.05,
            'comment': 0.05,
            'text': 0.0,
        }
        boosts.append(type_boosts.get(result.chunk_type, 0.0))
        
        # 4. Language preferences (boost popular languages)
        lang_boosts = {
            'python': 0.1,
            'javascript': 0.08,
            'typescript': 0.08,
            'java': 0.06,
            'cpp': 0.06,
            'go': 0.06,
            'rust': 0.06,
        }
        boosts.append(lang_boosts.get(result.language, 0.0))
        
        # 5. File name relevance
        file_name = result.file_path.lower()
        if any(word in file_name for word in query_words):
            boosts.append(0.1)
        
        # 6. Metadata relevance (function/class names)
        metadata = result.metadata
        if 'name' in metadata:
            name_lower = metadata['name'].lower()
            if any(word in name_lower for word in query_words):
                boosts.append(0.15)
        
        # 7. Penalize very short or very long chunks
        content_length = len(result.content)
        if content_length < 50:
            boosts.append(-0.1)  # Penalty for very short chunks
        elif content_length > 2000:
            boosts.append(-0.05)  # Small penalty for very long chunks
        
        # Calculate final score
        total_boost = sum(boosts)
        enhanced_score = base_score + total_boost
        
        # Ensure score stays in reasonable range
        return max(0.0, min(1.0, enhanced_score))
    
    def _extract_snippet(self, content: str, query: str) -> str:
        """Extract relevant snippet from content.
        
        Args:
            content: Full content to extract from
            query: Search query for context
            
        Returns:
            Extracted snippet
        """
        if len(content) <= self.snippet_length:
            return content
        
        # Try to find query matches for context
        query_lower = query.lower()
        content_lower = content.lower()
        
        # Find best match position
        match_pos = content_lower.find(query_lower)
        if match_pos == -1:
            # No exact match, look for individual words
            query_words = re.findall(r'\w+', query_lower)
            best_pos = 0
            best_score = 0
            
            for word in query_words:
                pos = content_lower.find(word)
                if pos != -1:
                    # Score based on how many query words are nearby
                    local_score = sum(
                        1 for w in query_words 
                        if w in content_lower[max(0, pos-100):pos+100]
                    )
                    if local_score > best_score:
                        best_score = local_score
                        best_pos = pos
            
            match_pos = best_pos
        
        # Extract snippet around match
        start_pos = max(0, match_pos - self.snippet_length // 2)
        end_pos = min(len(content), start_pos + self.snippet_length)
        
        # Adjust to word boundaries
        if start_pos > 0:
            # Find previous word boundary
            while start_pos > 0 and content[start_pos] not in ' \n\t':
                start_pos -= 1
            start_pos += 1  # Move past the space
        
        if end_pos < len(content):
            # Find next word boundary
            while end_pos < len(content) and content[end_pos] not in ' \n\t':
                end_pos += 1
        
        snippet = content[start_pos:end_pos]
        
        # Add ellipsis if truncated
        if start_pos > 0:
            snippet = '...' + snippet
        if end_pos < len(content):
            snippet = snippet + '...'
        
        return snippet
    
    def _highlight_snippet(self, snippet: str, query: str) -> str:
        """Add highlighting to snippet.
        
        Args:
            snippet: Text snippet to highlight
            query: Search query terms to highlight
            
        Returns:
            Snippet with highlighting markers
        """
        if not snippet or not query:
            return snippet
        
        highlighted = snippet
        query_words = re.findall(r'\w+', query.lower())
        
        # Sort by length (longest first) to avoid partial replacements
        query_words.sort(key=len, reverse=True)
        
        for word in query_words:
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(word) + r'\b'
            highlighted = re.sub(
                pattern,
                f'**{word}**',
                highlighted,
                flags=re.IGNORECASE
            )
        
        return highlighted
    
    def _deduplicate_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Remove duplicate and near-duplicate results.
        
        Args:
            results: List of search results
            
        Returns:
            Deduplicated results
        """
        if not results:
            return []
        
        deduplicated = []
        seen_content = set()
        
        for result in results:
            # Create a normalized version for comparison
            normalized = self._normalize_content(result.content)
            
            # Check for exact duplicates
            if normalized in seen_content:
                continue
            
            # Check for near-duplicates (high similarity)
            is_duplicate = False
            for existing in deduplicated:
                existing_normalized = self._normalize_content(existing.content)
                similarity = self._calculate_similarity(normalized, existing_normalized)
                
                if similarity > 0.9:  # 90% similarity threshold
                    # Keep the one with higher score
                    if result.score > existing.score:
                        # Replace existing with current
                        deduplicated.remove(existing)
                        seen_content.discard(existing_normalized)
                        break
                    else:
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                deduplicated.append(result)
                seen_content.add(normalized)
        
        return deduplicated
    
    def _normalize_content(self, content: str) -> str:
        """Normalize content for duplicate detection.
        
        Args:
            content: Content to normalize
            
        Returns:
            Normalized content
        """
        # Remove extra whitespace and normalize line endings
        normalized = re.sub(r'\s+', ' ', content.strip())
        
        # Remove common code formatting differences
        normalized = re.sub(r'[{}();,]', '', normalized)
        
        return normalized.lower()
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score between 0 and 1
        """
        if not text1 or not text2:
            return 0.0
        
        # Simple Jaccard similarity based on words
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 and not words2:
            return 1.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def group_results_by_file(self, results: List[SearchResult]) -> Dict[str, List[SearchResult]]:
        """Group search results by file path.
        
        Args:
            results: List of search results
            
        Returns:
            Dictionary mapping file paths to results
        """
        grouped = {}
        for result in results:
            file_path = result.file_path
            if file_path not in grouped:
                grouped[file_path] = []
            grouped[file_path].append(result)
        
        # Sort results within each file by line number
        for file_results in grouped.values():
            file_results.sort(key=lambda x: x.start_line)
        
        return grouped
    
    def get_search_stats(self, results: List[SearchResult]) -> Dict[str, Any]:
        """Get statistics about search results.
        
        Args:
            results: List of search results
            
        Returns:
            Dictionary with search statistics
        """
        if not results:
            return {
                'total_results': 0,
                'files_matched': 0,
                'languages': {},
                'chunk_types': {},
                'average_score': 0.0,
            }
        
        files = set(r.file_path for r in results)
        languages = {}
        chunk_types = {}
        
        for result in results:
            # Count languages
            lang = result.language
            languages[lang] = languages.get(lang, 0) + 1
            
            # Count chunk types
            chunk_type = result.chunk_type
            chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
        
        average_score = sum(r.score for r in results) / len(results)
        
        return {
            'total_results': len(results),
            'files_matched': len(files),
            'languages': languages,
            'chunk_types': chunk_types,
            'average_score': average_score,
            'score_range': {
                'min': min(r.score for r in results),
                'max': max(r.score for r in results),
            }
        }