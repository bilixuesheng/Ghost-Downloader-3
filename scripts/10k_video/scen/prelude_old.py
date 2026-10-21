# Old versions fetched an online OS-image catalog (sharepoint) at startup; return an empty catalog offline.
import json
try:
    import requests
    _get = requests.get
    class _R:
        status_code = 200
        content = json.dumps({"OS": []}).encode()
        text = content.decode()
        headers = {}
        def json(self): return {"OS": []}
        def raise_for_status(self): pass
    def get(url, *a, **k):
        if "sharepoint.com" in str(url):
            return _R()
        return _get(url, *a, **k)
    requests.get = get
except ImportError:
    pass
