def __getattr__(name):
    return (lambda *a, **k: 0)
