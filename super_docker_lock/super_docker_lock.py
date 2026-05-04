from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QDockWidget

from krita import Krita, Extension

from .functions import (
    hide_titlebars,
    restore_titlebars,
    hide_titlebar_for_dock,
    restore_titlebar_for_dock,
    remove_dock_from_cache,
)


class SuperDockerLockExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)

        self._action_state: bool = self._load_action_state()
        self._toggle_action = None
        self._main_window = None
        self._dock_widget_ids: set = set()
        self._window_ids: set = set()
        self._notifier_hooked: bool = False

    def setup(self) -> None:
        """Called by Krita after __init__; hook the notifier early."""
        self._register_document_listener()

    def createActions(self, window) -> None:
        """Called by Krita when it builds the menu / toolbar for *window*."""
        action = window.createAction(
            "super_docker_lock",
            "Super Docker Lock",
            "tools/scripts",
        )
        action.setCheckable(True)
        action.setIconText("")

        # Restore persisted state without firing the toggled signal yet.
        action.blockSignals(True)
        action.setChecked(self._action_state)
        action.blockSignals(False)

        action.toggled.connect(self._on_action_toggled)
        self._toggle_action = action

        self._update_action_icon(self._action_state)
        self._register_window(window)
        self._apply_action_state(self._action_state)
        self._register_document_listener()

    def _load_action_state(self) -> bool:
        raw = Krita.instance().readSetting("super_docker_lock", "enabled", "false")
        return str(raw).strip().lower() in ("1", "true", "yes", "on")

    def _persist_action_state(self, checked: bool) -> None:
        Krita.instance().writeSetting(
            "super_docker_lock",
            "enabled",
            "true" if checked else "false",
        )

    def _update_action_icon(self, locked: bool) -> None:
        if not self._toggle_action:
            return
        icon_name = "docker_lock_b" if locked else "docker_lock_a"
        self._toggle_action.setIcon(Krita.instance().icon(icon_name))

    def _on_action_toggled(self, checked: bool) -> None:
        self._action_state = checked
        self._update_action_icon(checked)
        self._persist_action_state(checked)
        self._apply_action_state(checked)

    def _apply_action_state(self, checked: bool) -> None:
        """
        Apply (or reverse) the title-bar hiding across the whole window.
        """
        if checked:
            hide_titlebars(self._main_window)
        else:
            restore_titlebars(self._main_window)

    def _register_document_listener(self) -> None:
        if self._notifier_hooked:
            return
        notifier = Krita.instance().notifier()
        if not notifier:
            return
        notifier.setActive(True)
        if hasattr(notifier, "windowCreated"):
            notifier.windowCreated.connect(self._on_window_created)
        if hasattr(notifier, "windowIsBeingCreated"):
            notifier.windowIsBeingCreated.connect(self._on_window_is_being_created)
        if hasattr(notifier, "viewCreated"):
            notifier.viewCreated.connect(self._on_view_created)
        self._notifier_hooked = True

    def _on_window_is_being_created(self, window) -> None:
        if window:
            self._register_window(window)

    def _on_window_created(self) -> None:
        window = Krita.instance().activeWindow()
        if window:
            self._register_window(window)
        if self._action_state:
            hide_titlebars(self._main_window)
        self._register_existing_dock_widgets()

    def _on_view_created(self, view) -> None:
        if view:
            window = view.window()
            if window:
                self._register_window(window)
        if self._action_state:
            hide_titlebars(self._main_window)
        self._register_existing_dock_widgets()

    def _register_window(self, window) -> None:
        if not window:
            return
        window_id = id(window)
        if window_id in self._window_ids:
            return
        self._window_ids.add(window_id)
        self._register_main_window(window.qwindow())

        window.activeViewChanged.connect(
            lambda *_args, _w=window: self._on_active_view_changed(_w)
        )
        if hasattr(window, "windowClosed"):
            window.windowClosed.connect(
                lambda _w=window: self._window_ids.discard(id(_w))
            )

    def _on_active_view_changed(self, _window) -> None:
        if self._action_state:
            hide_titlebars(self._main_window)

    def _register_main_window(self, main_window) -> None:
        if not main_window or self._main_window is main_window:
            return
        if self._main_window:
            self._main_window.removeEventFilter(self)
        self._main_window = main_window
        self._main_window.installEventFilter(self)
        self._register_existing_dock_widgets()

    def _register_existing_dock_widgets(self) -> None:
        if not self._main_window:
            return
        for dock in self._main_window.findChildren(QDockWidget):
            self._register_dock_widget(dock)

    def _register_dock_widget(self, dock: QDockWidget) -> None:
        dock_id = id(dock)
        if dock_id in self._dock_widget_ids:
            return
        self._dock_widget_ids.add(dock_id)
        dock.destroyed.connect(
            lambda _obj=None, _id=dock_id: self._on_dock_destroyed(_id)
        )
        dock.installEventFilter(self)

        if hasattr(dock, "topLevelChanged"):
            dock.topLevelChanged.connect(
                lambda _floating, _dock=dock: self._on_dock_top_level_changed(_dock)
            )

    def _on_dock_destroyed(self, dock_id: int) -> None:
        self._dock_widget_ids.discard(dock_id)
        remove_dock_from_cache(dock_id)

    def _on_dock_top_level_changed(self, dock: QDockWidget) -> None:
        if dock.isFloating():
            restore_titlebar_for_dock(dock)
        elif self._action_state:
            hide_titlebar_for_dock(dock)

    def eventFilter(self, watched, event) -> bool:
        etype = event.type()

        if etype == QEvent.ChildAdded:
            child = event.child()
            if isinstance(child, QDockWidget):
                self._register_dock_widget(child)
                if self._action_state:
                    hide_titlebar_for_dock(child)

        elif etype == QEvent.Show and isinstance(watched, QDockWidget):
            if self._action_state and not watched.isFloating():
                hide_titlebar_for_dock(watched)

        return False
