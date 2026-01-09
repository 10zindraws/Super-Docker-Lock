from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QDockWidget, QWidget

from krita import Krita, Extension

from .functions import (
    lock_docker_resizing,
    unlock_docker_resizing,
    update_docker_ui,
    update_docker_ui_for_dock,
    pulse_docker_lock_buttons,
)

class SuperDockerLockExtension(Extension):

    def __init__(self, parent):
        super().__init__(parent)

        self._action_state = self._load_action_state()
        self._toggle_action = None
        self._main_window = None
        self._dock_widget_ids = set()
        self._window_ids = set()
        self._notifier_hooked = False

    def setup(self):
        self._register_document_listener()

    def createActions(self,window):
        # menuLocation = "menu_custom/actions"
        menuLocation = "tools/scripts"

        action = window.createAction(
            "super_docker_lock",
            "Super Docker Lock",
            menuLocation)
        action.setCheckable(True)
        action.setIconText("")
        action.toggled.connect(self.action_toggleDockerLock)
        action.blockSignals(True)
        action.setChecked(self._action_state)
        action.blockSignals(False)
        self._toggle_action = action
        self._update_action_icon(self._action_state)
        self._register_window(window)
        self._apply_action_state(self._action_state)
        self._register_document_listener()

    def _load_action_state(self):
        raw_value = Krita.instance().readSetting("super_docker_lock", "enabled", "false")
        return str(raw_value).strip().lower() in ("1", "true", "yes", "on")

    def _persist_action_state(self, checked):
        Krita.instance().writeSetting(
            "super_docker_lock",
            "enabled",
            "true" if checked else "false",
        )

    def _update_action_icon(self, locked):
        if not self._toggle_action:
            return
        icon_name = "docker_lock_b" if locked else "docker_lock_a" #icons from krita's icon-library
        self._toggle_action.setIcon(Krita.instance().icon(icon_name))

    def action_toggleDockerLock(self, checked):
        self._apply_action_state(checked)
        self._action_state = checked
        self._update_action_icon(checked)
        self._persist_action_state(checked)

    def _apply_action_state(self, checked):
        if checked:
            lock_docker_resizing()
            self._sync_docker_ui()
        else:
            unlock_docker_resizing()
            update_docker_ui(self._main_window, False)
            pulse_docker_lock_buttons(self._main_window)

    def _sync_docker_ui(self):
        update_docker_ui(self._main_window, True)

    def _sync_docker_ui_for_dock(self, dock):
        update_docker_ui_for_dock(dock, self._main_window, self._action_state)

    def _register_document_listener(self):
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

    def _on_window_is_being_created(self, window):
        if window:
            self._register_window(window)

    def _on_window_created(self):
        window = Krita.instance().activeWindow()
        if window:
            self._register_window(window)
        if self._action_state:
            self._sync_docker_ui()
        self._register_existing_dock_widgets()

    def _on_view_created(self, view):
        if view:
            window = view.window()
            if window:
                self._register_window(window)
        if self._action_state:
            self._sync_docker_ui()
        self._register_existing_dock_widgets()

    def _register_window(self, window):
        if not window:
            return
        window_id = id(window)
        if window_id in self._window_ids:
            return
        self._window_ids.add(window_id)
        self._register_main_window(window.qwindow())
        window.activeViewChanged.connect(
            lambda *args, _win=window: self._on_active_view_changed(_win)
        )
        if hasattr(window, "windowClosed"):
            window.windowClosed.connect(
                lambda _win=window: self._window_ids.discard(id(_win))
            )

    def _on_active_view_changed(self, window):
        if not self._action_state:
            return
        self._sync_docker_ui()

    def _find_dock_widget(self, widget):
        current = widget
        while current and not isinstance(current, QDockWidget):
            if isinstance(current, QWidget):
                current = current.parentWidget()
            else:
                current = current.parent()
        return current if isinstance(current, QDockWidget) else None

    def _register_main_window(self, main_window):
        if not main_window or self._main_window is main_window:
            return
        if self._main_window:
            self._main_window.removeEventFilter(self)
        self._main_window = main_window
        self._main_window.installEventFilter(self)
        self._register_existing_dock_widgets()

    def _register_existing_dock_widgets(self):
        if not self._main_window:
            return
        for dock in self._main_window.findChildren(QDockWidget):
            self._register_dock_widget(dock)

    def _register_dock_widget(self, dock):
        dock_id = id(dock)
        if dock_id in self._dock_widget_ids:
            return
        self._dock_widget_ids.add(dock_id)
        dock.destroyed.connect(
            lambda _obj=None, dock_id=dock_id: self._dock_widget_ids.discard(dock_id)
        )
        dock.installEventFilter(self)
        if hasattr(dock, "dockLocationChanged"):
            dock.dockLocationChanged.connect(
                lambda _area, _dock=dock: self._on_dock_location_changed(_dock)
            )
        if hasattr(dock, "topLevelChanged"):
            dock.topLevelChanged.connect(
                lambda _floating, _dock=dock: self._on_dock_top_level_changed(_dock)
            )

    def _on_dock_location_changed(self, dock):
        if self._action_state:
            self._sync_docker_ui_for_dock(dock)

    def _on_dock_top_level_changed(self, dock):
        if self._action_state:
            self._sync_docker_ui_for_dock(dock)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.ChildAdded:
            child = event.child()
            if isinstance(child, QDockWidget):
                self._register_dock_widget(child)
                if self._action_state and not child.isFloating():
                    self._sync_docker_ui_for_dock(child)
            elif self._action_state and child:
                if child.metaObject().className() == "KoDockWidgetTitleBarButton":
                    dock = self._find_dock_widget(child)
                    if dock:
                        self._sync_docker_ui_for_dock(dock)
        elif event.type() == QEvent.Show and isinstance(watched, QDockWidget):
            if self._action_state and not watched.isFloating():
                self._sync_docker_ui_for_dock(watched)
        return False
