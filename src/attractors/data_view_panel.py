import numpy as np
from pyqtgraph.Qt import QtCore, QtWidgets

SAMPLE_COLUMNS = ("trajectory", "step", "t", "x", "y", "z")
MEASURE_COLUMNS = ("trajectory", "step", "t", "radius", "speed", "displacement")
DEFAULT_SAMPLE_SIZE = 2000


def _format_value(value):
    if value is None:
        return ""
    if isinstance(value, (float, np.floating)):
        if not np.isfinite(value):
            return str(value)
        return f"{float(value):.6g}"
    if isinstance(value, (int, np.integer)):
        return str(int(value))

    return str(value)


class RowTableModel(QtCore.QAbstractTableModel):
    """QTAbstractModel implementation.
    Override Qt rowCount, columnCount, headerData and data virtual methods
    """

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
    """QAbstractModel implementation to get sampled trajectory values
    Override Qt rowCount, columnCount, headerData and data virtual methods
    """

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

    def set_solutions(
        self,
        solutions,
        *,
        t_min=0.0,
        t_max=0.0,
        trajectory_specs=None,
    ):
        self.beginResetModel()
        self._solutions = [np.asarray(solution) for solution in solutions or []]
        self._t_min = float(t_min)
        self._default_t_max = float(t_max)
        self._trajectory_specs = list(trajectory_specs or [])
        self._rebuild_rows()
        self.endResetModel()

    def clear(self):
        self.set_solutions([])

    def set_sampled(self, sampled):
        sampled = bool(sampled)
        if sampled == self._sampled:
            return

        self.beginResetModel()
        self._sampled = sampled
        self._rebuild_rows()
        self.endResetModel()

    def set_sample_size(self, sample_size):
        sample_size = max(1, int(sample_size))
        if sample_size == self._sample_size:
            return

        self.beginResetModel()
        self._sample_size = sample_size
        self._rebuild_rows()
        self.endResetModel()

    def rowCount(self, parent=None):
        if parent is not None and parent.isValid():
            return 0

        return self._row_count

    def columnCount(self, parent=None):
        if parent is not None and parent.isValid():
            return 0

        return len(self._columns)

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None

        row_ref = self._row_ref(index.row())
        if row_ref is None:
            return None

        trajectory, step = row_ref
        column = self._columns[index.column()]

        return _format_value(self._value(trajectory, step, column))

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

    def set_solutions(
        self,
        solutions,
        *,
        t_min=0.0,
        t_max=0.0,
        trajectory_specs=None,
        config=None,
        values=None,
        partial=False,
    ):
        solution_arrays = [np.asarray(solution) for solution in solutions or []]
        specs = list(trajectory_specs or [])
        self._partial = bool(partial)
        self.model.set_solutions(
            solution_arrays,
            t_min=t_min,
            t_max=t_max,
            trajectory_specs=specs,
        )
        self.measures_model.set_solutions(
            solution_arrays,
            t_min=t_min,
            t_max=t_max,
            trajectory_specs=specs,
        )

        self.trajectory_model.set_rows(self._trajectory_rows(solutions, specs))
        self.parameter_model.set_rows(self._parameter_rows(config, values or {}))
        self.bounds_model.set_rows(self._bounds_rows(solutions))
        self._update_summary()

    def clear(self):
        self._partial = False
        self.model.clear()
        self.measures_model.clear()
        self.trajectory_model.clear()
        self.parameter_model.clear()
        self.bounds_model.clear()
        self.summary_label.setText("No data")

    @staticmethod
    def _table(model):
        table = QtWidgets.QTableView()
        table.setModel(model)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )

        return table

