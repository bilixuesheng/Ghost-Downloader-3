def FindWindow(*a): return 0
def ShowWindow(*a): return 0
def SetForegroundWindow(*a): return 0
def __getattr__(name):
    return lambda *a, **k: 0
