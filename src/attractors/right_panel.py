from pyqtgraph.Qt import QtCore, QtWidgets

from .custom_panel import CustomPanel
from .preset_panel import PresetPanel

# from .style import SIDE_PANEL
from .trajectory_panel import TrajectoryPanel


class _PanelTree(QtWidgets.QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._panel_items = {}
        self._sync_pending = False
        self.setObjectName("rightPanelTree")
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.setRootIsDecorated(True)
        self.setItemsExpandable(True)
        self.setIndentation(10)
        self.setVerticalScrollMode(
            QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.itemExpanded.connect(self._sync_embedded_size)
        self.itemCollapsed.connect(self._sync_embedded_size)

    def add_panel(self, title, widget, *, expanded=True):
        root = QtWidgets.QTreeWidgetItem([str(title)])
        root.setFlags(root.flags() & ~QtCore.Qt.ItemFlag.ItemIsSelectable)
        root.setSizeHint(0, QtCore.QSize(0, 28))
        self.addTopLevelItem(root)

        child = QtWidgets.QTreeWidgetItem()
        child.setFlags(child.flags() & ~QtCore.Qt.ItemFlag.ItemIsSelectable)
        root.addChild(child)
        child.setSizeHint(0, widget.sizeHint())
        self.setItemWidget(child, 0, widget)
        widget.installEventFilter(self)
        self._panel_items[widget] = child
        root.setExpanded(bool(expanded))

        return root

    def eventFilter(self, watched, event):
        if watched in self._panel_items and event.type() in {
            QtCore.QEvent.Type.LayoutRequest,
            QtCore.QEvent.Type.Resize,
            QtCore.QEvent.Type.Show,
        }:
            self.schedule_embedded_size_sync()

        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.schedule_embedded_size_sync()

    def schedule_embedded_size_sync(self):
        if self._sync_pending:
            return
        self._sync_pending = True
        QtCore.QTimer.singleShot(0, self.sync_embedded_sizes)

    def sync_embedded_sizes(self):
        self._sync_pending = False
        for widget, item in self._panel_items.items():
            item.setSizeHint(0, widget.sizeHint())

        self.scheduleDelayedItemsLayout()

    def _sync_embedded_size(self, item):
        for index in range(item.childCount()):
            child = item.child(index)
            widget = self.itemWidget(child, 0)
            if widget is not None:
                child.setSizeHint(0, widget.sizeHint())

        self.schedule_embedded_size_sync()


class RightPanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("rightPanel")
        self.setMinimumWidth(260)
        # self.setStyleSheet(SIDE_PANEL)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 4, 4)
        layout.setSpacing(0)

        self.tree = _PanelTree()
        layout.addWidget(self.tree)

        self.trajectory_panel = TrajectoryPanel(collapsible=False)
        self.preset_panel = PresetPanel()
        self.custom_panel = CustomPanel(collapsible=False)

        self.trajectory_root = self.tree.add_panel(
            "Trajectories",
            self.trajectory_panel,
            expanded=True,
        )
        self.preset_root = self.tree.add_panel(
            "Presets",
            self.preset_panel,
            expanded=True,
        )
        self.custom_root = self.tree.add_panel(
            "Custom",
            self.custom_panel,
            expanded=False,
        )
        self.trajectory_panel.layout_changed.connect(
            self.tree.schedule_embedded_size_sync
        )

        self.set_current_attractor("")

    def set_current_attractor(self, name):
        custom = name == "Custom"
        self.custom_root.setHidden(not custom)
        self.custom_panel.setVisible(custom)
        if custom:
            self.custom_root.setExpanded(True)
