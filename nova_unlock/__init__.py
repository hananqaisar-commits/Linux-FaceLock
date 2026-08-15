__version__ = "3.2"

# NovaUnlock v3.2 Stable Release
try:
    from nova_unlock.vision.liveness    import LivenessDetector
    from nova_unlock.ui.theme_manager   import ThemeManager, get_theme
except ImportError:
    pass
