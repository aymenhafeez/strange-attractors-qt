from pyqtgraph.Qt import QtCore, QtWidgets

from .custom_panel import CustomPanel
from .docking import AppDock as Dock
from .docking import AppDockArea as DockArea
from .preset_panel import PresetPanel
from .trajectory_panel import TrajectoryPanel


def _scrollable(widget):
    scroll = QtWidgets.QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(widget)

    return scroll


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
        root = QtWidgets.QTreeWidgetItem([title])
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
        root.setExpanded(expanded)

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

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(2, 4, 4, 4)
        layout.setSpacing(0)

        self.dock_area = DockArea()
        layout.addWidget(self.dock_area)

        self.trajectory_panel = TrajectoryPanel(collapsible=False)
        self.preset_panel = PresetPanel()
        self.custom_panel = CustomPanel(collapsible=False)

        self.trajectory_dock = Dock("Trajectories", size=(1, 260), closable=False)
        self.trajectory_dock.addWidget(self.trajectory_panel)
        self.dock_area.addDock(self.trajectory_dock)

        self.preset_dock = Dock("Presets", size=(1, 260), closable=False)
        self.preset_dock.addWidget(_scrollable(self.preset_panel))
        self.dock_area.addDock(
            self.preset_dock, position="bottom", relativeTo=self.trajectory_dock
        )

        self.custom_dock = Dock("Custom", size=(1, 300), closable=False)
        self.custom_dock.addWidget(_scrollable(self.custom_panel))
        self.dock_area.addDock(
            self.custom_dock, position="below", relativeTo=self.preset_dock
        )

        self.set_current_attractor("")

    def set_current_attractor(self, name):
        if name == "Custom":
            self.custom_dock.raiseDock()
        else:
            self.preset_dock.raiseDock()
