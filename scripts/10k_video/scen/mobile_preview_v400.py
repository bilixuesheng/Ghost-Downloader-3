"""Desktop preview of the v4.0.0 Android UI (mirrors android/preview.py added in v4.1.0)."""
import os, sys
ROOT = os.getcwd()
sys.path.insert(0, os.path.join(ROOT, "android"))
sys.path.insert(0, ROOT)

import app.platform.android as _android
_android.nativeLibraryDir = lambda: ""
_android.isStorageGranted = lambda: True
_android.requestStoragePermission = lambda: None
_android.isSystemDark = lambda: False
for _n in ("sharedText", "clearShare"):
    setattr(_android, _n, lambda *a, **k: None)
import app.platform.android_notification as _notif
_notif.isNotificationEnabled = lambda: True
_notif.requestNotificationPermission = lambda: None

if __name__ == "__main__":
    from main import setupEnvironment
    from PySide6.QtWidgets import QApplication
    setupEnvironment()
    application = QApplication(sys.argv)
    from app.view.mobile import setupAndroid
    setupAndroid()
    import app.assets.resources  # noqa: F401
    from app.models.pack import PackConfig
    from app.services.coroutine_runner import coroutineRunner
    from app.services.feature_service import featureService
    from app.services.task_service import taskService
    coroutineRunner.start()
    featureService.load()
    PackConfig.load()
    taskService.resumeSaved()
    featureService.start()
    from app.view.mobile.window import MobileMainWindow
    from app.view.mobile.device import setupTouchScrolling
    window = MobileMainWindow()
    window.resize(400, 800)
    window.show()
    setupTouchScrolling(window)
    sys.exit(application.exec())
