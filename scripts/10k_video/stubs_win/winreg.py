# Minimal stub so Windows-only code paths import on Linux; every lookup fails like a missing key.
HKEY_CURRENT_USER = 1; HKEY_LOCAL_MACHINE = 2; HKEY_CLASSES_ROOT = 0
KEY_READ = 0x20019; KEY_WRITE = 0x20006; KEY_ALL_ACCESS = 0xF003F; KEY_SET_VALUE = 2; KEY_QUERY_VALUE = 1
REG_SZ = 1; REG_DWORD = 4; REG_EXPAND_SZ = 2
def _fail(*a, **k): raise OSError(2, "stub winreg")
OpenKey = OpenKeyEx = QueryValueEx = CreateKey = CreateKeyEx = SetValueEx = DeleteValue = DeleteKey = EnumKey = EnumValue = QueryValue = _fail
def CloseKey(*a): pass
class HKEYType:
    pass
