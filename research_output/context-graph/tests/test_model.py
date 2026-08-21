import pytest

from context_graph.model import (ROOT_ID, Node, NodeType, SecondaryEdge, validate_new_node,
                                 would_create_cycle)


def _exists(ids):
    return lambda i: i in ids


def test_root_needs_no_parent():
    validate_new_node(Node(title="r", type=NodeType.ROOT, id=ROOT_ID), _exists(set()))


def test_nonroot_requires_parent():
    with pytest.raises(ValueError):
        validate_new_node(Node(title="x"), _exists(set()))


def test_parent_must_exist():
    with pytest.raises(ValueError):
        validate_new_node(Node(title="x", parent_id="p"), _exists(set()))


def test_valid_child_ok():
    validate_new_node(Node(title="x", parent_id="p"), _exists({"p"}))


def test_cycle_detection():
    parents = {"b": "a", "a": ROOT_ID, ROOT_ID: None}
    get = parents.get
    assert would_create_cycle("a", "b", get) is True     # a under its own descendant
    assert would_create_cycle("a", ROOT_ID, get) is False


def test_edge_current_by_default():
    assert SecondaryEdge(source_id="a", target_id="b").is_current
