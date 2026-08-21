"""context-graph — a dynamically traversable context knowledge graph for agent long-term memory."""

from .assembly import AssemblyResult, assemble
from .embeddings import EmbeddingProvider, HashingEmbedder, cosine, find_entry_points
from .export_obsidian import export_vault
from .graph import Authority, ContextGraph
from .locking import LockConflict, LockManager
from .model import Node, NodeType, SecondaryEdge
from .sample import build_sample
from .store.base import StorageBackend
from .store.memory_store import MemoryStore

__all__ = [
    "ContextGraph", "Authority", "Node", "SecondaryEdge", "NodeType",
    "StorageBackend", "MemoryStore", "EmbeddingProvider", "HashingEmbedder", "cosine",
    "find_entry_points", "assemble", "AssemblyResult", "LockManager", "LockConflict",
    "export_vault", "build_sample",
]
__version__ = "0.1.0"
