"""Database schema for memory management system."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)

Base = declarative_base()


class KVStore(Base):
    """Key-value storage for project settings and metadata."""
    
    __tablename__ = "kv_store"
    
    key = Column(String(255), primary_key=True)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<KVStore(key='{self.key}', value='{self.value[:50]}...')>"


class ConversationHistory(Base):
    """Storage for conversation messages and context."""
    
    __tablename__ = "conversation_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), nullable=False, index=True)
    message_id = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    metadata = Column(Text)  # JSON string for additional data
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<ConversationHistory(id={self.id}, role='{self.role}', session='{self.session_id}')>"


class FileMetadata(Base):
    """Metadata about files in the workspace."""
    
    __tablename__ = "file_metadata"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(String(1024), nullable=False, unique=True, index=True)
    file_hash = Column(String(64), nullable=False)  # SHA-256 hash
    file_size = Column(Integer, nullable=False)
    language = Column(String(50))
    summary = Column(Text)  # AI-generated summary
    last_modified = Column(DateTime, nullable=False)
    last_analyzed = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<FileMetadata(id={self.id}, path='{self.file_path}', lang='{self.language}')>"


class DecisionLog(Base):
    """Log of agent decisions and reasoning."""
    
    __tablename__ = "decision_log"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), nullable=False, index=True)
    decision_type = Column(String(100), nullable=False)  # 'tool_call', 'plan_step', 'file_edit', etc.
    context = Column(Text)  # Context that led to the decision
    decision = Column(Text, nullable=False)  # The actual decision made
    reasoning = Column(Text)  # Agent's reasoning
    outcome = Column(String(50))  # 'success', 'failure', 'partial'
    metadata = Column(Text)  # JSON string for additional data
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<DecisionLog(id={self.id}, type='{self.decision_type}', outcome='{self.outcome}')>"


class ExecutionLog(Base):
    """Log of tool executions and operations."""
    
    __tablename__ = "execution_log"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), nullable=False, index=True)
    operation = Column(String(100), nullable=False)  # 'file_write', 'git_commit', 'command_run', etc.
    target = Column(String(1024))  # File path, command, etc.
    details = Column(Text)  # Operation details and parameters
    result = Column(Text)  # Operation result
    success = Column(Boolean, nullable=False)
    duration_ms = Column(Integer)  # Execution time in milliseconds
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<ExecutionLog(id={self.id}, op='{self.operation}', success={self.success})>"


class ProjectSummary(Base):
    """High-level project summaries and insights."""
    
    __tablename__ = "project_summary"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    summary_type = Column(String(100), nullable=False)  # 'architecture', 'recent_changes', 'key_files'
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    confidence = Column(Integer, default=50)  # Confidence score 0-100
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<ProjectSummary(id={self.id}, type='{self.summary_type}', title='{self.title}')>"


class DatabaseManager:
    """Manages database connections and schema operations."""
    
    def __init__(self, db_path: Path, echo: bool = False):
        """Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
            echo: Whether to echo SQL statements (for debugging)
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create engine with connection pooling for SQLite
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            echo=echo,
            poolclass=StaticPool,
            connect_args={
                "check_same_thread": False,
                "timeout": 30,
            },
        )
        
        # Configure SQLite for better performance
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            # Enable WAL mode for better concurrency
            cursor.execute("PRAGMA journal_mode=WAL")
            # Enable foreign key constraints
            cursor.execute("PRAGMA foreign_keys=ON")
            # Set synchronous mode for better performance
            cursor.execute("PRAGMA synchronous=NORMAL")
            # Set cache size (negative value = KB)
            cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
            # Set temp store to memory
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.close()
        
        # Create session factory
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        logger.info(f"Initialized database manager for {db_path}")
    
    def create_tables(self):
        """Create all database tables."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise
    
    def drop_tables(self):
        """Drop all database tables (for testing/reset)."""
        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.info("Database tables dropped successfully")
        except Exception as e:
            logger.error(f"Failed to drop database tables: {e}")
            raise
    
    def get_session(self):
        """Get a database session."""
        return self.SessionLocal()
    
    def close(self):
        """Close database connections."""
        try:
            self.engine.dispose()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")
    
    def get_table_stats(self) -> Dict[str, int]:
        """Get row counts for all tables.
        
        Returns:
            Dictionary mapping table names to row counts
        """
        stats = {}
        
        try:
            with self.get_session() as session:
                for table_name in Base.metadata.tables.keys():
                    result = session.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = result.scalar()
                    stats[table_name] = count
        except Exception as e:
            logger.error(f"Failed to get table stats: {e}")
            stats["error"] = str(e)
        
        return stats
    
    def vacuum_database(self):
        """Vacuum the database to reclaim space and optimize performance."""
        try:
            with self.engine.connect() as conn:
                conn.execute("VACUUM")
            logger.info("Database vacuumed successfully")
        except Exception as e:
            logger.error(f"Failed to vacuum database: {e}")
            raise
    
    def get_database_size(self) -> int:
        """Get database file size in bytes.
        
        Returns:
            Database file size in bytes
        """
        try:
            return self.db_path.stat().st_size
        except Exception as e:
            logger.error(f"Failed to get database size: {e}")
            return 0