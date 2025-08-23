"""Code chunking with AST parsing for semantic code analysis."""

import ast
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Optional tree-sitter import
try:
    import tree_sitter
    from tree_sitter import Language, Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    tree_sitter = None
    Language = None
    Parser = None
    TREE_SITTER_AVAILABLE = False

from agent.models.base import FileChange

logger = logging.getLogger(__name__)


@dataclass
class ChunkResult:
    """Result of code chunking operation."""
    content: str
    start_line: int
    end_line: int
    chunk_type: str  # 'function', 'class', 'method', 'import', 'comment', 'text'
    language: str
    file_path: str
    metadata: Dict[str, Any]
    
    @property
    def line_count(self) -> int:
        """Get number of lines in chunk."""
        return self.end_line - self.start_line + 1
    
    @property
    def identifier(self) -> str:
        """Get unique identifier for this chunk."""
        return f"{self.file_path}:{self.start_line}-{self.end_line}"


class LanguageDetector:
    """Detect programming language from file extension and content."""
    
    EXTENSION_MAP = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.java': 'java',
        '.cpp': 'cpp',
        '.cc': 'cpp',
        '.cxx': 'cpp',
        '.c': 'c',
        '.h': 'c',
        '.hpp': 'cpp',
        '.cs': 'csharp',
        '.go': 'go',
        '.rs': 'rust',
        '.rb': 'ruby',
        '.php': 'php',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.scala': 'scala',
        '.sh': 'bash',
        '.bash': 'bash',
        '.zsh': 'bash',
        '.fish': 'bash',
        '.ps1': 'powershell',
        '.sql': 'sql',
        '.html': 'html',
        '.htm': 'html',
        '.xml': 'xml',
        '.css': 'css',
        '.scss': 'scss',
        '.sass': 'sass',
        '.less': 'less',
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.toml': 'toml',
        '.ini': 'ini',
        '.cfg': 'ini',
        '.conf': 'ini',
        '.md': 'markdown',
        '.markdown': 'markdown',
        '.rst': 'rst',
        '.txt': 'text',
        '.log': 'text',
        '.dockerfile': 'dockerfile',
        '.gitignore': 'text',
        '.gitattributes': 'text',
        '.env': 'text',
    }
    
    @classmethod
    def detect_language(cls, file_path: Path, content: Optional[str] = None) -> str:
        """Detect programming language from file path and content.
        
        Args:
            file_path: Path to the file
            content: File content (optional, for content-based detection)
            
        Returns:
            Detected language name
        """
        # Check extension first
        extension = file_path.suffix.lower()
        if extension in cls.EXTENSION_MAP:
            return cls.EXTENSION_MAP[extension]
        
        # Check filename patterns
        filename = file_path.name.lower()
        if filename in ['dockerfile', 'makefile', 'rakefile', 'gemfile']:
            return filename
        
        if filename.startswith('.'):
            # Hidden config files
            return 'text'
        
        # Content-based detection if available
        if content:
            return cls._detect_from_content(content)
        
        # Default to text
        return 'text'
    
    @classmethod
    def _detect_from_content(cls, content: str) -> str:
        """Detect language from content patterns."""
        content_lower = content.lower()
        
        # Shebang detection
        if content.startswith('#!'):
            first_line = content.split('\n')[0]
            if 'python' in first_line:
                return 'python'
            elif 'node' in first_line or 'javascript' in first_line:
                return 'javascript'
            elif 'bash' in first_line or 'sh' in first_line:
                return 'bash'
        
        # Language-specific patterns
        patterns = {
            'python': [r'def\s+\w+\s*\(', r'class\s+\w+', r'import\s+\w+', r'from\s+\w+\s+import'],
            'javascript': [r'function\s+\w+\s*\(', r'const\s+\w+\s*=', r'let\s+\w+\s*=', r'var\s+\w+\s*='],
            'java': [r'public\s+class\s+\w+', r'private\s+\w+', r'public\s+static\s+void\s+main'],
            'cpp': [r'#include\s*<', r'int\s+main\s*\(', r'class\s+\w+\s*{'],
            'go': [r'package\s+\w+', r'func\s+\w+\s*\(', r'import\s*\('],
            'rust': [r'fn\s+\w+\s*\(', r'struct\s+\w+', r'impl\s+\w+'],
        }
        
        for lang, lang_patterns in patterns.items():
            if any(re.search(pattern, content) for pattern in lang_patterns):
                return lang
        
        return 'text'


class CodeChunker:
    """Language-aware code chunking with AST parsing."""
    
    def __init__(self, max_chunk_size: int = 1000, overlap_size: int = 100):
        """Initialize code chunker.
        
        Args:
            max_chunk_size: Maximum characters per chunk
            overlap_size: Overlap between adjacent chunks
        """
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size
        self.language_detector = LanguageDetector()
        
        # Initialize tree-sitter parsers
        self.parsers = {}
        self._init_parsers()
    
    def _init_parsers(self):
        """Initialize tree-sitter parsers for supported languages."""
        if not TREE_SITTER_AVAILABLE:
            logger.info("Tree-sitter not available, using fallback parsers")
            # Use Python AST for Python files
            self.parsers['python'] = 'python_ast'
            return
        
        try:
            # Try to load tree-sitter languages
            languages = {
                'python': 'tree_sitter_python',
                'javascript': 'tree_sitter_javascript', 
                'typescript': 'tree_sitter_typescript',
            }
            
            for lang_name, module_name in languages.items():
                try:
                    # This would normally load the compiled language
                    # For now, we'll use Python AST for Python files
                    if lang_name == 'python':
                        self.parsers[lang_name] = 'python_ast'
                    logger.debug(f"Loaded parser for {lang_name}")
                except Exception as e:
                    logger.debug(f"Could not load parser for {lang_name}: {e}")
                    
        except Exception as e:
            logger.warning(f"Failed to initialize tree-sitter parsers: {e}")
    
    def chunk_file(self, file_path: Path, content: str) -> List[ChunkResult]:
        """Chunk a file into semantic segments.
        
        Args:
            file_path: Path to the file
            content: File content
            
        Returns:
            List of chunk results
        """
        try:
            # Skip empty content
            if not content.strip():
                return []
            
            language = self.language_detector.detect_language(file_path, content)
            
            # Use language-specific chunking if available
            if language == 'python' and 'python' in self.parsers:
                return self._chunk_python_ast(file_path, content)
            else:
                return self._chunk_generic(file_path, content, language)
                
        except Exception as e:
            logger.error(f"Failed to chunk file {file_path}: {e}")
            # Fallback to generic chunking
            return self._chunk_generic(file_path, content, 'text')
    
    def _chunk_python_ast(self, file_path: Path, content: str) -> List[ChunkResult]:
        """Chunk Python code using AST parsing."""
        chunks = []
        
        try:
            tree = ast.parse(content)
            lines = content.split('\n')
            
            # Extract top-level constructs
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    chunk = self._extract_python_function(node, lines, file_path)
                    if chunk:
                        chunks.append(chunk)
                        
                elif isinstance(node, ast.ClassDef):
                    chunk = self._extract_python_class(node, lines, file_path)
                    if chunk:
                        chunks.append(chunk)
                        
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    chunk = self._extract_python_import(node, lines, file_path)
                    if chunk:
                        chunks.append(chunk)
            
            # Fill gaps with generic chunks
            chunks = self._fill_gaps_with_generic(chunks, content, file_path, 'python')
            
        except SyntaxError as e:
            logger.warning(f"Python syntax error in {file_path}: {e}")
            return self._chunk_generic(file_path, content, 'python')
        
        return sorted(chunks, key=lambda x: x.start_line)
    
    def _extract_python_function(self, node: ast.FunctionDef, lines: List[str], file_path: Path) -> Optional[ChunkResult]:
        """Extract a Python function as a chunk."""
        try:
            start_line = node.lineno
            end_line = node.end_lineno or start_line
            
            # Include decorators
            if node.decorator_list:
                start_line = min(d.lineno for d in node.decorator_list)
            
            content = '\n'.join(lines[start_line-1:end_line])
            
            # Extract metadata
            metadata = {
                'name': node.name,
                'type': 'async_function' if isinstance(node, ast.AsyncFunctionDef) else 'function',
                'args': [arg.arg for arg in node.args.args],
                'decorators': [ast.unparse(d) for d in node.decorator_list] if node.decorator_list else [],
                'docstring': ast.get_docstring(node),
            }
            
            return ChunkResult(
                content=content,
                start_line=start_line,
                end_line=end_line,
                chunk_type='function',
                language='python',
                file_path=str(file_path),
                metadata=metadata
            )
            
        except Exception as e:
            logger.debug(f"Failed to extract function {node.name}: {e}")
            return None
    
    def _extract_python_class(self, node: ast.ClassDef, lines: List[str], file_path: Path) -> Optional[ChunkResult]:
        """Extract a Python class as a chunk."""
        try:
            start_line = node.lineno
            end_line = node.end_lineno or start_line
            
            # Include decorators
            if node.decorator_list:
                start_line = min(d.lineno for d in node.decorator_list)
            
            content = '\n'.join(lines[start_line-1:end_line])
            
            # Extract methods
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(item.name)
            
            # Extract metadata
            metadata = {
                'name': node.name,
                'type': 'class',
                'bases': [ast.unparse(base) for base in node.bases],
                'decorators': [ast.unparse(d) for d in node.decorator_list] if node.decorator_list else [],
                'methods': methods,
                'docstring': ast.get_docstring(node),
            }
            
            return ChunkResult(
                content=content,
                start_line=start_line,
                end_line=end_line,
                chunk_type='class',
                language='python',
                file_path=str(file_path),
                metadata=metadata
            )
            
        except Exception as e:
            logger.debug(f"Failed to extract class {node.name}: {e}")
            return None
    
    def _extract_python_import(self, node: ast.Import, lines: List[str], file_path: Path) -> Optional[ChunkResult]:
        """Extract Python import statements as a chunk."""
        try:
            start_line = node.lineno
            end_line = node.end_lineno or start_line
            
            content = '\n'.join(lines[start_line-1:end_line])
            
            # Extract imported modules
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
                import_type = 'import'
            else:  # ast.ImportFrom
                modules = [alias.name for alias in node.names]
                import_type = 'from_import'
            
            metadata = {
                'type': import_type,
                'modules': modules,
                'module': getattr(node, 'module', None),
                'level': getattr(node, 'level', 0),
            }
            
            return ChunkResult(
                content=content,
                start_line=start_line,
                end_line=end_line,
                chunk_type='import',
                language='python',
                file_path=str(file_path),
                metadata=metadata
            )
            
        except Exception as e:
            logger.debug(f"Failed to extract import: {e}")
            return None
    
    def _chunk_generic(self, file_path: Path, content: str, language: str) -> List[ChunkResult]:
        """Generic text-based chunking for unsupported languages."""
        chunks = []
        lines = content.split('\n')
        
        current_chunk = []
        current_size = 0
        start_line = 1
        
        for i, line in enumerate(lines, 1):
            line_size = len(line) + 1  # +1 for newline
            
            # Check if adding this line would exceed chunk size
            if current_size + line_size > self.max_chunk_size and current_chunk:
                # Create chunk from current content
                chunk_content = '\n'.join(current_chunk)
                chunks.append(ChunkResult(
                    content=chunk_content,
                    start_line=start_line,
                    end_line=i - 1,
                    chunk_type='text',
                    language=language,
                    file_path=str(file_path),
                    metadata={'line_count': len(current_chunk)}
                ))
                
                # Start new chunk with overlap
                overlap_lines = max(0, min(self.overlap_size // 50, len(current_chunk) // 2))
                if overlap_lines > 0:
                    current_chunk = current_chunk[-overlap_lines:]
                    current_size = sum(len(line) + 1 for line in current_chunk)
                    start_line = i - overlap_lines
                else:
                    current_chunk = []
                    current_size = 0
                    start_line = i
            
            current_chunk.append(line)
            current_size += line_size
        
        # Add final chunk if there's remaining content
        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            chunks.append(ChunkResult(
                content=chunk_content,
                start_line=start_line,
                end_line=len(lines),
                chunk_type='text',
                language=language,
                file_path=str(file_path),
                metadata={'line_count': len(current_chunk)}
            ))
        
        return chunks
    
    def _fill_gaps_with_generic(self, ast_chunks: List[ChunkResult], content: str, file_path: Path, language: str) -> List[ChunkResult]:
        """Fill gaps between AST chunks with generic text chunks."""
        if not ast_chunks:
            return self._chunk_generic(file_path, content, language)
        
        all_chunks = []
        lines = content.split('\n')
        covered_lines = set()
        
        # Mark lines covered by AST chunks
        for chunk in ast_chunks:
            for line_num in range(chunk.start_line, chunk.end_line + 1):
                covered_lines.add(line_num)
        
        # Find gaps and create generic chunks
        gap_start = None
        for line_num in range(1, len(lines) + 1):
            if line_num not in covered_lines:
                if gap_start is None:
                    gap_start = line_num
            else:
                if gap_start is not None:
                    # End of gap, create chunk
                    gap_content = '\n'.join(lines[gap_start-1:line_num-1])
                    if gap_content.strip():  # Only create chunk if not empty
                        all_chunks.append(ChunkResult(
                            content=gap_content,
                            start_line=gap_start,
                            end_line=line_num - 1,
                            chunk_type='text',
                            language=language,
                            file_path=str(file_path),
                            metadata={'gap_fill': True}
                        ))
                    gap_start = None
        
        # Handle final gap
        if gap_start is not None:
            gap_content = '\n'.join(lines[gap_start-1:])
            if gap_content.strip():
                all_chunks.append(ChunkResult(
                    content=gap_content,
                    start_line=gap_start,
                    end_line=len(lines),
                    chunk_type='text',
                    language=language,
                    file_path=str(file_path),
                    metadata={'gap_fill': True}
                ))
        
        # Combine AST chunks and gap chunks
        all_chunks.extend(ast_chunks)
        return sorted(all_chunks, key=lambda x: x.start_line)
    
    def should_index_file(self, file_path: Path) -> bool:
        """Determine if a file should be indexed.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file should be indexed
        """
        # Skip hidden files and directories
        if any(part.startswith('.') for part in file_path.parts):
            # Allow some common config files
            allowed_hidden = {'.env', '.gitignore', '.gitattributes', '.dockerignore'}
            if file_path.name not in allowed_hidden:
                return False
        
        # Skip common build/cache directories
        skip_dirs = {
            'node_modules', '__pycache__', '.git', '.svn', '.hg',
            'build', 'dist', 'target', 'bin', 'obj', '.vscode',
            '.idea', '.pytest_cache', '.mypy_cache', '.tox',
            'venv', 'env', '.env', 'virtualenv'
        }
        
        if any(part in skip_dirs for part in file_path.parts):
            return False
        
        # Skip binary files by extension
        binary_extensions = {
            '.exe', '.dll', '.so', '.dylib', '.a', '.lib',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico',
            '.mp3', '.mp4', '.avi', '.mov', '.wav', '.pdf',
            '.zip', '.tar', '.gz', '.rar', '.7z', '.bin',
            '.pyc', '.pyo', '.class', '.jar', '.war'
        }
        
        if file_path.suffix.lower() in binary_extensions:
            return False
        
        # Check file size (skip very large files)
        try:
            if file_path.exists() and file_path.stat().st_size > 1024 * 1024:  # 1MB
                return False
        except (OSError, IOError):
            return False
        
        return True
    
    def get_file_stats(self, chunks: List[ChunkResult]) -> Dict[str, Any]:
        """Get statistics about chunked file.
        
        Args:
            chunks: List of chunks for a file
            
        Returns:
            Dictionary with file statistics
        """
        if not chunks:
            return {}
        
        total_lines = max(chunk.end_line for chunk in chunks)
        total_chars = sum(len(chunk.content) for chunk in chunks)
        
        chunk_types = {}
        for chunk in chunks:
            chunk_types[chunk.chunk_type] = chunk_types.get(chunk.chunk_type, 0) + 1
        
        return {
            'total_chunks': len(chunks),
            'total_lines': total_lines,
            'total_characters': total_chars,
            'chunk_types': chunk_types,
            'language': chunks[0].language,
            'average_chunk_size': total_chars // len(chunks) if chunks else 0,
        }