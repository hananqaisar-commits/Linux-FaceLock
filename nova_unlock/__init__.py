__version__ = "2.21"

# NovaUnlock v2.012
try:
    from nova_unlock.vision.liveness    import LivenessDetector
    from nova_unlock.ui.theme_manager   import ThemeManager, get_theme
except ImportError:
    pass
