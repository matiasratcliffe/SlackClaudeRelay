"""context-graph — a dynamically traversable context knowledge graph for agent long-term memory."""

from .assembly import AssemblyResult, assemble
from .embeddings import EmbeddingProvider, HashingEmbedder, cosine, find_entry_points
from .export_obsidian import export_vault
from .graph import Authority, ContextGraph
from .locking import LockConflict, LockManager
from .model import MountLink, Node, NodeType, SecondaryEdge
from .sample import build_sample
from .store.base import StorageBackend
from .store.memory_store import MemoryStore
from .structure import OPINIONATED_STRUCTURE, deploy_structure

__all__ = [
    "ContextGraph", "Authority", "Node", "SecondaryEdge", "MountLink", "NodeType",
    "StorageBackend", "MemoryStore", "EmbeddingProvider", "HashingEmbedder", "cosine",
    "find_entry_points", "assemble", "AssemblyResult", "LockManager", "LockConflict",
    "export_vault", "build_sample", "deploy_structure", "OPINIONATED_STRUCTURE",
]
__version__ = "0.1.0"
