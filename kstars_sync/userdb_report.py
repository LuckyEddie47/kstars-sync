"""
userdb_report.py

Presentation helpers for KStars userdb.sqlite change summaries.

This module does not inspect or compare databases. It only converts known
userdb.sqlite table names into clearer display labels. Unknown tables are
reported using their raw SQLite names so newer KStars schemas remain visible.
"""

from __future__ import annotations


TABLE_LABELS: dict[str, str] = {
    "SkyMapViews": "Sky map views",
    "Version": "Database version",
    "collimationoverlayelements": "Collimation overlay elements",
    "customdrivers": "Custom drivers",
    "darkframe": "Dark frames",
    "driver": "Drivers",
    "dslr": "DSLR cameras",
    "dslrlens": "DSLR lenses",
    "effectivefov": "Effective fields of view",
    "eyepiece": "Eyepieces",
    "filter": "Filters",
    "flags": "Flags",
    "fov": "Fields of view",
    "hips": "HiPS data",
    "horizon_1": "Artificial horizon data (1)",
    "horizon_2": "Artificial horizon data (2)",
    "horizon_3": "Artificial horizon data (3)",
    "horizons": "Artificial horizons",
    "imageOverlays": "Image overlays",
    "imagingPlanner": "Imaging planner",
    "lens": "Lenses",
    "logentry": "Log entries",
    "opticaltraindevices": "Optical train devices",
    "opticaltrains": "Optical trains",
    "opticaltrainsettings": "Optical train settings",
    "profile": "Profiles",
    "profilesettings": "Profile settings",
    "telescope": "Telescopes",
    "user": "User data",
    "wishlist": "Wishlist",
}


def format_changed_tables(table_names: list[str]) -> str:
    """
    Format changed userdb.sqlite tables for terminal display.

    Known KStars table names are shown using a clearer label followed by the
    exact SQLite table name. Unknown tables are shown unchanged.

    Parameters
    ----------
    table_names
        Table names reported by the SQLite comparison layer.

    Returns
    -------
    str
        One display line per table, preserving the supplied order.
    """

    lines: list[str] = []

    for table_name in table_names:
        label = TABLE_LABELS.get(table_name)

        if label is None:
            lines.append(table_name)
        else:
            lines.append(f"{label} ({table_name})")

    return "\n".join(lines)
