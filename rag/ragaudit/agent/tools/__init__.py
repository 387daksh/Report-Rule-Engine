"""Tool groups and registry assembly."""

from __future__ import annotations

from ragaudit.agent.registry import ToolRegistry
from ragaudit.agent.tools import navigate, query, search


def build_registry() -> ToolRegistry:
    """Assemble the full tool registry.

    Groups are added here; the loop decides which to *expose* to the model at
    any point (progressive disclosure). Phase 2 ships navigate, query and
    search — the read core. Later phases register analyse, quality, render,
    export and meta against this same registry.
    """
    registry = ToolRegistry()
    navigate.register(registry)
    query.register(registry)
    search.register(registry)
    return registry
