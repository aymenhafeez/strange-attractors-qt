import numpy as np
from pyqtgraph.Qt import QtCore, QtWidgets

SAMPLE_COLUMNS = ("trajectory", "step", "t", "x", "y", "z")
MEASURE_COLUMNS = ("trajectory", "step", "t", "radius", "speed", "displacement")
DEFAULT_SAMPLE_SIZE = 2000


class RowTableModel(QtCore.QAbstractTableModel):
    def __init__(self, columns, parent=None):
        super().__init__(parent)
        self._columns = tuple(columns)
        self._rows = []

    def set_rows(self, rows):
        self.beginResetModel()
        self._rows = list(rows or [])
        self.endResetModel()

    def clear(self):
        self.set_rows([])

    def rowCount(self, parent=None):
        if parent is not None and parent.isValid():
            return 0

        return len(self._rows)

    def columnCount(self, parent=None):
        if parent is not None and parent.isValid():
            return 0

        return len(self._columns)

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None

        try:
            column = self._columns[index.column()]
            value = self._rows[index.row()].get(column)
        except IndexError:
            return None

        return _format_value(value)

    def headerData(
        self,
        section,
        orientation,
        role=QtCore.Qt.ItemDataRole.DisplayRole,
    ):
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == QtCore.Qt.Orientation.Horizontal:
            try:
                return self._columns[section]
            except IndexError:
                return None

        return str(section + 1)


class TrajectoryTableModel(QtCore.QAbstractTableModel):
    def __init__(self, columns=SAMPLE_COLUMNS, parent=None):
        super().__init__(parent)
        self._columns = tuple(columns)
        self._solutions = []
        self._t_min = 0.0
        self._default_t_max = 0.0
        self._trajectory_specs = []
        self._sampled = True
        self._sample_size = DEFAULT_SAMPLE_SIZE
        self._sample_indices = []
        self._cumulative_rows = []
        self._row_count = 0


class DataViewPanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dataViewPanel")

        self.model = TrajectoryTableModel(parent=self)
        self.measures_model = TrajectoryTableModel(MEASURE_COLUMNS, self)
        self.trajectory_model = RowTableModel(
            (
                "trajectory",
                "length",
                "initial_x",
                "initial_y",
                "initial_z",
                "final_x",
                "final_y",
                "final_z",
            ),
            self,
        )
        self.parameter_model = RowTableModel(
            ("name", "value", "default", "min", "max", "step"),
            self,
        )
        self.bounds_model = RowTableModel(("axis", "min", "max", "range"), self)

        self.summary_label = QtWidgets.QLabel("No data")
        self.summary_label.setObjectName("dataViewSummary")
        self._partial = False

        self.sample_mode = QtWidgets.QCheckBox("Sample")
        self.sample_mode.setChecked(True)
        self.sample_mode.toggled.connect(self._on_sample_mode_toggled)

        self.sample_size = QtWidgets.QSpinBox()
        self.sample_size.setRange(10, 50000)
        self.sample_size.setSingleStep(100)
        self.sample_size.setValue(DEFAULT_SAMPLE_SIZE)
        self.sample_size.valueChanged.connect(self._on_sample_size_changed)

        self.export_button = QtWidgets.QPushButton("Export")
        self.export_button.clicked.connect(self._export_current_tab)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(6)
        # toolbar.addWidget(self.summary_label, 1)
        toolbar.addWidget(self.sample_mode)
        toolbar.addWidget(self.export_button)
        toolbar.addWidget(self.sample_size)

        self.table = self._table(self.model)
        self.measures_table = self._table(self.measures_model)
        self.trajectory_table = self._table(self.trajectory_model)
        self.parameter_table = self._table(self.parameter_model)
        self.bounds_table = self._table(self.bounds_model)

        samples_tab = QtWidgets.QWidget()
        samples_layout = QtWidgets.QVBoxLayout(samples_tab)
        samples_layout.setContentsMargins(0, 0, 0, 0)
        samples_layout.setSpacing(6)
        # samples_layout.addLayout(toolbar)
        samples_layout.addWidget(self.table)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(samples_tab, "Samples")
        self.tabs.addTab(self.trajectory_table, "Trajectories")
        self.tabs.addTab(self.parameter_table, "Parameters")
        self.tabs.addTab(self.bounds_table, "Bounds")
        self.tabs.addTab(self.measures_table, "Measures")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(6)
        layout.addLayout(toolbar)
        layout.addWidget(self.tabs)
