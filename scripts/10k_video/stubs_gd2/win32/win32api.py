# Linux stand-in: Windows API calls become no-ops, constants are 0.
def __getattr__(name):
    if name[:1].isupper() and name.upper() == name:
        return 0
    return lambda *a, **k: 0
