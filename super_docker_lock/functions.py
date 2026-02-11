from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAbstractButton, QDockWidget, QSizePolicy

from krita import Krita

# --- Helper Functions ---

_LOCK_BUTTON_CLASS_NAME = "KoDockWidgetTitleBarButton"
_TITLE_BAR_COLLAPSED_PROPERTY = "_super_docker_lock_titlebar_collapsed"
_TITLE_BAR_MIN_HEIGHT_PROPERTY = "_super_docker_lock_titlebar_min_height"
_TITLE_BAR_MAX_HEIGHT_PROPERTY = "_super_docker_lock_titlebar_max_height"
_TITLE_BAR_STYLE_PROPERTY = "_super_docker_lock_titlebar_style"
_TITLE_BAR_STYLE_ATTR_PROPERTY = "_super_docker_lock_titlebar_style_attr"
_TITLE_BAR_SIZE_POLICY_PROPERTY = "_super_docker_lock_titlebar_size_policy"
_TITLE_BAR_MARGINS_PROPERTY = "_super_docker_lock_titlebar_margins"
_TITLE_BAR_LAYOUT_MARGINS_PROPERTY = "_super_docker_lock_titlebar_layout_margins"
_TITLE_BAR_LAYOUT_SPACING_PROPERTY = "_super_docker_lock_titlebar_layout_spacing"
_DOCK_SIZE_CONSTRAINTS_PROPERTY = "_super_docker_lock_dock_size_constraints"
_TITLE_BAR_COLLAPSE_STYLE = (
    "min-height:0px; max-height:0px; height:0px; padding:0px; margin:0px;"
)

def _get_dock_widgets_in_area(main_window, dock_area):
    """
    Get all dock widgets in the specified area that are not floating.
    """
    if not main_window:
        return []
    return [
        dock for dock in main_window.findChildren(QDockWidget)
        if main_window.dockWidgetArea(dock) == dock_area and not dock.isFloating()
    ]

def _get_tab_group_key(main_window, dock_widget):
    """
    Create a unique identifier for a tab group based on its members.
    Considers only non-floating docks.
    """
    if not main_window or not dock_widget or dock_widget.isFloating():
        return tuple()
    
    # Start with the given dock widget if it's not floating
    all_docks_in_group = [dock_widget]
    
    # Add tabified docks, ensuring they are also not floating
    # Note: tabifiedDockWidgets itself returns a list of QDockWidget
    tabified_list = main_window.tabifiedDockWidgets(dock_widget)
    for tab_dock in tabified_list:
        if not tab_dock.isFloating():
            all_docks_in_group.append(tab_dock)
            
    # Sort by object name to ensure consistent ordering
    all_docks_in_group.sort(key=lambda d: d.objectName())
    return tuple(d.objectName() for d in all_docks_in_group)

# --- Dock Lock Icon Helpers ---

def _is_grouped_docker(main_window, dock_widget):
    if not main_window or not dock_widget or dock_widget.isFloating():
        return False
    tabified_list = [
        dock for dock in main_window.tabifiedDockWidgets(dock_widget)
        if not dock.isFloating()
    ]
    return len(tabified_list) > 0
    
def _has_utility_title_bar(dock_widget):
    """Check if the dock widget uses a KisUtilityTitleBar which contains
    functional controls (e.g. Animation Timeline, Animation Curves) that
    must remain visible even when the titlebar would normally be collapsed."""
    title_bar = dock_widget.titleBarWidget()
    if not title_bar:
        return False
    return title_bar.inherits("KisUtilityTitleBar")

def _is_lock_docker_button(button):
    if not button:
        return False

    if button.metaObject().className() != _LOCK_BUTTON_CLASS_NAME:
        return False

    text_bits = []
    for value in (
        button.toolTip(),
        button.text(),
        button.accessibleName(),
        button.accessibleDescription(),
        button.statusTip(),
    ):
        if value:
            text_bits.append(value.lower())

    if not text_bits:
        return True

    return any("lock" in text for text in text_bits)


def _refresh_title_bar_layout(dock_widget):
    title_bar = dock_widget.titleBarWidget()
    if not title_bar:
        return
    layout = title_bar.layout()
    if layout:
        layout.invalidate()
    title_bar.updateGeometry()
    title_bar.update()
    dock_widget.updateGeometry()

def _store_title_bar_state(title_bar):
    title_bar.setProperty(
        _TITLE_BAR_MIN_HEIGHT_PROPERTY, int(title_bar.minimumHeight())
    )
    title_bar.setProperty(
        _TITLE_BAR_MAX_HEIGHT_PROPERTY, int(title_bar.maximumHeight())
    )
    title_bar.setProperty(_TITLE_BAR_STYLE_PROPERTY, title_bar.styleSheet())
    title_bar.setProperty(
        _TITLE_BAR_STYLE_ATTR_PROPERTY,
        bool(title_bar.testAttribute(Qt.WA_StyleSheet)),
    )
    policy = title_bar.sizePolicy()
    title_bar.setProperty(
        _TITLE_BAR_SIZE_POLICY_PROPERTY,
        (policy.horizontalPolicy(), policy.verticalPolicy(), int(policy.controlType())),
    )
    margins = title_bar.contentsMargins()
    title_bar.setProperty(
        _TITLE_BAR_MARGINS_PROPERTY,
        (int(margins.left()), int(margins.top()), int(margins.right()), int(margins.bottom())),
    )
    layout = title_bar.layout()
    if layout:
        layout_margins = layout.contentsMargins()
        title_bar.setProperty(
            _TITLE_BAR_LAYOUT_MARGINS_PROPERTY,
            (
                int(layout_margins.left()),
                int(layout_margins.top()),
                int(layout_margins.right()),
                int(layout_margins.bottom()),
            ),
        )
        title_bar.setProperty(_TITLE_BAR_LAYOUT_SPACING_PROPERTY, int(layout.spacing()))
    else:
        title_bar.setProperty(_TITLE_BAR_LAYOUT_MARGINS_PROPERTY, None)
        title_bar.setProperty(_TITLE_BAR_LAYOUT_SPACING_PROPERTY, None)

def _restore_title_bar_state(title_bar):
    stored_min = title_bar.property(_TITLE_BAR_MIN_HEIGHT_PROPERTY)
    stored_max = title_bar.property(_TITLE_BAR_MAX_HEIGHT_PROPERTY)
    stored_style = title_bar.property(_TITLE_BAR_STYLE_PROPERTY)
    stored_style_attr = title_bar.property(_TITLE_BAR_STYLE_ATTR_PROPERTY)
    stored_policy = title_bar.property(_TITLE_BAR_SIZE_POLICY_PROPERTY)
    stored_margins = title_bar.property(_TITLE_BAR_MARGINS_PROPERTY)
    stored_layout_margins = title_bar.property(_TITLE_BAR_LAYOUT_MARGINS_PROPERTY)
    stored_layout_spacing = title_bar.property(_TITLE_BAR_LAYOUT_SPACING_PROPERTY)

    if stored_style is None:
        stored_style = ""
    if stored_style_attr is None:
        stored_style_attr = False

    title_bar.setStyleSheet(stored_style)
    if not stored_style_attr and not stored_style:
        title_bar.setAttribute(Qt.WA_StyleSheet, False)

    if stored_min is None:
        stored_min = 0
    if stored_max is None:
        stored_max = 16777215

    title_bar.setMinimumHeight(int(stored_min))
    title_bar.setMaximumHeight(int(stored_max))

    if stored_policy and isinstance(stored_policy, (tuple, list)) and len(stored_policy) >= 2:
        policy = QSizePolicy(int(stored_policy[0]), int(stored_policy[1]))
        if len(stored_policy) >= 3:
            policy.setControlType(QSizePolicy.ControlType(int(stored_policy[2])))
        title_bar.setSizePolicy(policy)

    if stored_margins and isinstance(stored_margins, (tuple, list)) and len(stored_margins) >= 4:
        title_bar.setContentsMargins(
            int(stored_margins[0]),
            int(stored_margins[1]),
            int(stored_margins[2]),
            int(stored_margins[3]),
        )
    layout = title_bar.layout()
    if layout:
        if (
            stored_layout_margins
            and isinstance(stored_layout_margins, (tuple, list))
            and len(stored_layout_margins) >= 4
        ):
            layout.setContentsMargins(
                int(stored_layout_margins[0]),
                int(stored_layout_margins[1]),
                int(stored_layout_margins[2]),
                int(stored_layout_margins[3]),
            )
        if stored_layout_spacing is not None:
            layout.setSpacing(int(stored_layout_spacing))

def _clear_title_bar_state(title_bar):
    title_bar.setProperty(_TITLE_BAR_MIN_HEIGHT_PROPERTY, None)
    title_bar.setProperty(_TITLE_BAR_MAX_HEIGHT_PROPERTY, None)
    title_bar.setProperty(_TITLE_BAR_STYLE_PROPERTY, None)
    title_bar.setProperty(_TITLE_BAR_STYLE_ATTR_PROPERTY, None)
    title_bar.setProperty(_TITLE_BAR_SIZE_POLICY_PROPERTY, None)
    title_bar.setProperty(_TITLE_BAR_MARGINS_PROPERTY, None)
    title_bar.setProperty(_TITLE_BAR_LAYOUT_MARGINS_PROPERTY, None)
    title_bar.setProperty(_TITLE_BAR_LAYOUT_SPACING_PROPERTY, None)

def _repolish_widget(widget):
    style = widget.style()
    if not style:
        return
    style.unpolish(widget)
    style.polish(widget)

def _apply_title_bar_collapse_style(title_bar):
    stored_style = title_bar.property(_TITLE_BAR_STYLE_PROPERTY)
    if stored_style:
        combined = "{}\n{}".format(stored_style, _TITLE_BAR_COLLAPSE_STYLE)
    else:
        combined = _TITLE_BAR_COLLAPSE_STYLE
    title_bar.setStyleSheet(combined)

def _set_title_bar_visible(dock_widget, visible):
    title_bar = dock_widget.titleBarWidget()
    if not title_bar:
        return
    desired_collapsed = not visible
    current_state = title_bar.property(_TITLE_BAR_COLLAPSED_PROPERTY)
    if current_state is None and visible:
        return
    if current_state == desired_collapsed:
        return

    if not visible:
        _store_title_bar_state(title_bar)
        _apply_title_bar_collapse_style(title_bar)
        title_bar.setContentsMargins(0, 0, 0, 0)
        layout = title_bar.layout()
        if layout:
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
        title_bar.setMinimumHeight(0)
        title_bar.setMaximumHeight(0)
        title_bar.setFixedHeight(0)
        title_bar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        title_bar.setVisible(True)
    else:
        _restore_title_bar_state(title_bar)
        title_bar.setVisible(True)
        _repolish_widget(title_bar)
        _clear_title_bar_state(title_bar)

    title_bar.setProperty(
        _TITLE_BAR_COLLAPSED_PROPERTY, desired_collapsed if not visible else None
    )
    _refresh_title_bar_layout(dock_widget)


def _iter_lock_buttons(dock_widget):
    title_bar = dock_widget.titleBarWidget()
    search_root = title_bar if title_bar else dock_widget

    for button in search_root.findChildren(QAbstractButton):
        if _is_lock_docker_button(button):
            yield button


def _set_lock_buttons_state(dock_widget, checked, hidden):
    changed = False
    desired_visible = not hidden
    for button in _iter_lock_buttons(dock_widget):
        if button.isCheckable() and button.isChecked() != checked:
            button.setChecked(checked)
            changed = True

        if button.isVisible() != desired_visible:
            button.setVisible(desired_visible)
            changed = True
        if button.isEnabled() != desired_visible:
            button.setEnabled(desired_visible)
            changed = True

    if changed:
        _refresh_title_bar_layout(dock_widget)

def _set_lock_buttons_checked(dock_widget, checked):
    changed = False
    for button in _iter_lock_buttons(dock_widget):
        if not button.isCheckable():
            continue
        if button.isChecked() != checked:
            button.setChecked(checked)
            changed = True

    if changed:
        _refresh_title_bar_layout(dock_widget)

def _set_lock_buttons_visible(dock_widget, visible):
    changed = False
    for button in _iter_lock_buttons(dock_widget):
        if button.isVisible() != visible:
            button.setVisible(visible)
            changed = True
        if button.isEnabled() != visible:
            button.setEnabled(visible)
            changed = True
    if changed:
        _refresh_title_bar_layout(dock_widget)

def _store_dock_size_constraints(dock_widget):
    if dock_widget.property(_DOCK_SIZE_CONSTRAINTS_PROPERTY) is not None:
        return
    dock_widget.setProperty(
        _DOCK_SIZE_CONSTRAINTS_PROPERTY,
        (
            int(dock_widget.minimumWidth()),
            int(dock_widget.maximumWidth()),
            int(dock_widget.minimumHeight()),
            int(dock_widget.maximumHeight()),
        ),
    )

def _restore_dock_size_constraints(dock_widget):
    stored = dock_widget.property(_DOCK_SIZE_CONSTRAINTS_PROPERTY)
    if not stored or not isinstance(stored, (tuple, list)) or len(stored) < 4:
        dock_widget.setProperty(_DOCK_SIZE_CONSTRAINTS_PROPERTY, None)
        return False
    dock_widget.setMinimumWidth(int(stored[0]))
    dock_widget.setMaximumWidth(int(stored[1]))
    dock_widget.setMinimumHeight(int(stored[2]))
    dock_widget.setMaximumHeight(int(stored[3]))
    dock_widget.setProperty(_DOCK_SIZE_CONSTRAINTS_PROPERTY, None)
    return True

# --- Main Functionality ---

def _resolve_main_window(main_window=None):
    if main_window:
        return main_window
    inst = Krita.instance()
    win = inst.activeWindow()
    if not win:
        return None
    return win.qwindow()

def _update_docker_ui_for_dock(main_window, dock_widget, lock_enabled):
    if not main_window or not dock_widget:
        return
    if dock_widget.isFloating():
        _set_title_bar_visible(dock_widget, True)
        _set_lock_buttons_visible(dock_widget, True)
        return

    if lock_enabled:
        if _is_grouped_docker(main_window, dock_widget) and not _has_utility_title_bar(dock_widget):
            _set_title_bar_visible(dock_widget, False)
        else:
            _set_title_bar_visible(dock_widget, True)
        _set_lock_buttons_state(dock_widget, True, True)
    else:
        _set_lock_buttons_state(dock_widget, False, False)
        _set_title_bar_visible(dock_widget, True)

def update_docker_ui(main_window=None, lock_enabled=False):
    """
    Updates lock buttons and grouped title bars for all dockers.
    """
    main_window = _resolve_main_window(main_window)
    if not main_window:
        return
    for dock in main_window.findChildren(QDockWidget):
        _update_docker_ui_for_dock(main_window, dock, lock_enabled)

def update_docker_ui_for_dock(dock_widget, main_window=None, lock_enabled=False):
    """
    Updates lock buttons and grouped title bar for a single docker.
    """
    main_window = _resolve_main_window(main_window)
    if not main_window:
        return
    _update_docker_ui_for_dock(main_window, dock_widget, lock_enabled)



def lock_docker_resizing():
    """
    Locks the size of currently visible and non-floating dockers in all standard dock areas.
    Width is locked for Left/Right areas, Height for Top/Bottom areas,
    based on the dimensions of the active dock in each tab group.
    """

    inst = Krita.instance()
    win = inst.activeWindow()
    if not win: return
    view = win.activeView()
    if not view: return
    qmwin = win.qwindow()
    if not qmwin: return

    krita_instance = inst
    main_window = qmwin

    # print("Attempting to lock docker resizing...")

    areas_to_process = [
        Qt.LeftDockWidgetArea,
        Qt.RightDockWidgetArea,
        Qt.TopDockWidgetArea,
        Qt.BottomDockWidgetArea
    ]

    MAX_QT_DIMENSION = 16777215  # Maximum value for QWidget dimensions

    for area in areas_to_process:
        dock_widgets_in_area = _get_dock_widgets_in_area(main_window, area)
        
        # Filter for dock widgets that are actually visible on screen
        active_rendered_docks = [
            dock for dock in dock_widgets_in_area
            if dock.isVisible() and not dock.visibleRegion().isEmpty()
        ]

        if not active_rendered_docks:
            continue
        
        processed_groups = set()
        for active_dock_in_group in active_rendered_docks:
            # active_dock_in_group is the one currently drawn, use its size as reference
            
            group_key = _get_tab_group_key(main_window, active_dock_in_group)
            if not group_key or group_key in processed_groups: # Skip if no valid group or already processed
                continue
            processed_groups.add(group_key)

            # Get all docks that belong to this same tab group
            # The key already represents all docks in the group, but we need the QDockWidget objects
            # Re-fetch based on one member (active_dock_in_group)
            tab_group_docks = [active_dock_in_group] + \
                              [d for d in main_window.tabifiedDockWidgets(active_dock_in_group) if not d.isFloating()]


            if area in (Qt.LeftDockWidgetArea, Qt.RightDockWidgetArea):
                current_width = active_dock_in_group.width()
                for dock in tab_group_docks:
                    if dock.isVisible(): # Apply only to visible docks in the tab group
                        _store_dock_size_constraints(dock)
                        dock.setMinimumWidth(current_width)
                        dock.setMaximumWidth(current_width)
                        # Keep height flexible
                        dock.setMinimumHeight(0)
                        dock.setMaximumHeight(MAX_QT_DIMENSION)
            elif area in (Qt.TopDockWidgetArea, Qt.BottomDockWidgetArea):
                current_height = active_dock_in_group.height()
                for dock in tab_group_docks:
                    if dock.isVisible(): # Apply only to visible docks in the tab group
                        _store_dock_size_constraints(dock)
                        dock.setMinimumHeight(current_height)
                        dock.setMaximumHeight(current_height)
                        # Keep width flexible
                        dock.setMinimumWidth(0)
                        dock.setMaximumWidth(MAX_QT_DIMENSION)
    # print("Docker resizing locked for visible, non-floating dockers.")


def unlock_docker_resizing():
    """
    Unlocks the size of all non-floating dockers, restoring their ability to be resized.
    """

    inst = Krita.instance()
    win = inst.activeWindow()
    if not win: return
    view = win.activeView()
    if not view: return
    qmwin = win.qwindow()
    if not qmwin: return

    krita_instance = inst
    main_window = qmwin

    # print("Attempting to unlock docker resizing...")

    all_dock_widgets = main_window.findChildren(QDockWidget)

    for dock in all_dock_widgets:
        if not dock.isFloating(): # Only affect non-floating dockers
            _restore_dock_size_constraints(dock)
            
    # print("Docker resizing unlocked for non-floating dockers.")


def enable_docker_lock_buttons(main_window=None):
    """
    Toggles on all docked "Lock Docker" buttons and hides them.
    """
    main_window = _resolve_main_window(main_window)
    if not main_window:
        return
    for dock in main_window.findChildren(QDockWidget):
        if dock.isFloating():
            continue
        _set_lock_buttons_state(dock, True, True)


def disable_docker_lock_buttons(main_window=None):
    """
    Toggles off all docked "Lock Docker" buttons and shows them.
    """
    main_window = _resolve_main_window(main_window)
    if not main_window:
        return
    for dock in main_window.findChildren(QDockWidget):
        if dock.isFloating():
            continue
        _set_lock_buttons_state(dock, False, False)

def pulse_docker_lock_buttons(main_window=None):
    """
    Quickly toggles all docked "Lock Docker" buttons on then off to refresh layout.
    """
    main_window = _resolve_main_window(main_window)
    if not main_window:
        return
    dock_widgets = [
        dock for dock in main_window.findChildren(QDockWidget)
        if not dock.isFloating()
    ]
    for dock in dock_widgets:
        _set_lock_buttons_checked(dock, True)
    for dock in dock_widgets:
        _set_lock_buttons_checked(dock, False)


def update_grouped_docker_title_bars(main_window=None, hide_grouped=False):
    """
    Hides title bars for dockers that are tab-grouped when enabled.
    """
    main_window = _resolve_main_window(main_window)
    if not main_window:
        return
    for dock in main_window.findChildren(QDockWidget):
        if dock.isFloating():
            _set_title_bar_visible(dock, True)
            continue
        is_grouped = _is_grouped_docker(main_window, dock)
        if hide_grouped and is_grouped and not _has_utility_title_bar(dock):
            _set_title_bar_visible(dock, False)
        else:
            _set_title_bar_visible(dock, True)
