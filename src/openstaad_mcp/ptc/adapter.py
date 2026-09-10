"""Explicit PTC catalog; discovery requires no COM connection."""

from typing import Any

from openstaad_mcp.ptc.analysis import AnalysisTools
from openstaad_mcp.ptc.design import DesignTools
from openstaad_mcp.ptc.geometry import GeometryTools
from openstaad_mcp.ptc.loads import LoadTools
from openstaad_mcp.ptc.properties import PropertyTools
from openstaad_mcp.ptc.registry import ToolRegistry
from openstaad_mcp.ptc.supports import SupportTools


class OpenSTAADAdapter(GeometryTools, PropertyTools, LoadTools, SupportTools, AnalysisTools, DesignTools):
    """Host-only facade retaining the existing adapter API."""


def build_registry(staad: Any = None) -> ToolRegistry:
    """Register explicit host methods. With no staad, discovery needs no COM connection."""
    adapter = OpenSTAADAdapter(staad)
    registry = ToolRegistry()
    bindings = {
        "geometry.get_plates": adapter.get_plates,
        "geometry.get_solids": adapter.get_solids,
        "geometry.get_groups": adapter.get_groups,
        "geometry.get_connected_members": adapter.get_connected_members,
        "properties.get_member_properties_full": adapter.get_member_properties_full,
        "properties.get_plate_properties": adapter.get_plate_properties,
        "properties.get_material_properties": adapter.get_material_properties,
        "properties.get_member_releases": adapter.get_member_releases,
        "loads.get_combinations": adapter.get_combinations,
        "loads.get_reference_load_cases": adapter.get_reference_load_cases,
        "analysis.get_member_forces_at_distance": adapter.get_member_forces_at_distance,
        "analysis.get_member_force_extrema": adapter.get_member_force_extrema,
        "analysis.get_max_section_displacements": adapter.get_max_section_displacements,
        "analysis.get_plate_center_results": adapter.get_plate_center_results,
        "analysis.get_plate_principal_stresses": adapter.get_plate_principal_stresses,
        "analysis.get_plate_von_mises_stresses": adapter.get_plate_von_mises_stresses,
        "design.get_member_results": adapter.get_member_results,
        "geometry.get_base_units": adapter.get_base_units,
        "geometry.get_node_count": adapter.get_node_count,
        "geometry.get_member_count": adapter.get_member_count,
        "geometry.get_nodes": adapter.get_nodes,
        "geometry.get_members": adapter.get_members,
        "properties.get_member_properties": adapter.get_member_properties,
        "loads.get_load_cases": adapter.get_load_cases,
        "supports.get_supports": adapter.get_supports,
        "analysis.are_results_available": adapter.are_results_available,
        "analysis.get_units": adapter.get_units,
        "analysis.get_member_forces": adapter.get_member_forces,
        "analysis.get_node_displacements": adapter.get_node_displacements,
        "analysis.get_support_reactions": adapter.get_support_reactions,
        "design.get_utilization": adapter.get_utilization,
    }
    for name, function in bindings.items():
        registry.register(name, function)
    return registry
