"""eval/ — second caller over the existing Scribe seams (design.md §6, §7).

This package is NOT part of the runtime. It drives build_scribe / Scribe through
the same public interfaces that CLI and the UI use — it never monkeypatches
scribe/ internals. If it ever needs to reach past an interface to get a metric,
the seam is wrong (design.md §6: "stop and report it").
"""
