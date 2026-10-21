# Linux stand-in: registry reads succeed and describe "no proxy configured".
HKEY_CURRENT_USER = 1; HKEY_LOCAL_MACHINE = 2; HKEY_CLASSES_ROOT = 0
KEY_READ = 0x20019; KEY_WRITE = 0x20006; KEY_ALL_ACCESS = 0xF003F; KEY_SET_VALUE = 2; KEY_QUERY_VALUE = 1
REG_SZ = 1; REG_DWORD = 4; REG_EXPAND_SZ = 2
class _Key:
    def __enter__(self): return self
    def __exit__(self, *a): pass
def OpenKey(*a, **k): return _Key()
OpenKeyEx = CreateKey = CreateKeyEx = OpenKey
def QueryValueEx(key, name):
    return (0, REG_DWORD) if name == "ProxyEnable" else ("", REG_SZ)
def SetValueEx(*a, **k): pass
def DeleteValue(*a, **k): pass
def CloseKey(*a): pass
