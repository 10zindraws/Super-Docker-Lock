from PyQt5.QtWidgets import QDockWidget, QWidget
from krita import Krita

_ANIMATION_TIMELINE_TITLE = "Animation Timeline"

_original_titlebars: dict = {}


def _get_main_window():
    inst = Krita.instance()
    win = inst.activeWindow()
    if not win:
        return None
    return win.qwindow()


def _should_hide(dock: QDockWidget) -> bool:
    return dock.windowTitle() != _ANIMATION_TIMELINE_TITLE


def hide_titlebar_for_dock(dock: QDockWidget) -> None:
    if not dock:
        return
    if dock.isFloating():
        return
    if not _should_hide(dock):
        return

    dock_id = id(dock)
    if dock_id not in _original_titlebars:
        _original_titlebars[dock_id] = dock.titleBarWidget()

    dock.setTitleBarWidget(QWidget())


def restore_titlebar_for_dock(dock: QDockWidget) -> None:
    if not dock:
        return
    dock_id = id(dock)
    if dock_id in _original_titlebars:
        original = _original_titlebars.pop(dock_id)
        dock.setTitleBarWidget(original)   # None → restores Qt default


def remove_dock_from_cache(dock_id: int) -> None:
    _original_titlebars.pop(dock_id, None)


def hide_titlebars(main_window=None) -> None:
    if main_window is None:
        main_window = _get_main_window()
    if not main_window:
        return
    for dock in main_window.findChildren(QDockWidget):
        hide_titlebar_for_dock(dock)


def restore_titlebars(main_window=None) -> None:
    if main_window is None:
        main_window = _get_main_window()
    if not main_window:
        return
    for dock in main_window.findChildren(QDockWidget):
        restore_titlebar_for_dock(dock)
