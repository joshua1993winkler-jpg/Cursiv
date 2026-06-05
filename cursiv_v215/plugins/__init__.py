"""
Cursiv plugin registry package.
"""

try:
    from cursiv_v215.plugins.registry import (
        ALL_PLUGINS,
        PluginManifest,
        show_status,
        get_commands,
        get_by_category,
    )
except Exception:
    pass
