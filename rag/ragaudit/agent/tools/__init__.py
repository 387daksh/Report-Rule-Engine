"""Tool groups and registry assembly."""

from __future__ import annotations

from ragaudit.agent.registry import ToolRegistry
from ragaudit.agent.tools import analyse, meta, navigate, query, quality, search


def build_registry() -> ToolRegistry:
    """Assemble the full tool registry.

    Groups are added here; the loop decides which to *expose* to the model at
    any point (progressive disclosure). navigate/query/search are the base
    read set; analyse/quality/meta are unlocked via use_toolset. Render and
    export register in later phases against this same registry.
    """
    registry = ToolRegistry()
    navigate.register(registry)
    query.register(registry)
    search.register(registry)
    analyse.register(registry)
    quality.register(registry)
    meta.register(registry)
    return registry
