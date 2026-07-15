from pyqtgraph.Qt import QtCore

from .worker import LyapunovWorker, SolveWorker


class SolveManager(QtCore.QObject):
    solutions_ready = QtCore.pyqtSignal(object, bool)
    lyapunov_ready = QtCore.pyqtSignal(object, float, object, object)
    _solve_request = QtCore.pyqtSignal(object, dict, list, int, bool, float)
    _lyapunov_request = QtCore.pyqtSignal(object, dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._solver_worker = SolveWorker()
        self._solver_thread = QtCore.QThread()
        self._solver_worker.moveToThread(self._solver_thread)
        self._solver_thread.start()
        self._solve_request.connect(self._solver_worker.solve)
        self._solver_worker.result_ready.connect(self.solutions_ready)

        self._lyapunov_worker = LyapunovWorker()
        self._lyapunov_thread = QtCore.QThread()
        self._lyapunov_worker.moveToThread(self._lyapunov_thread)
        self._lyapunov_thread.start()
        self._lyapunov_request.connect(self._lyapunov_worker.compute)
        self._lyapunov_worker.lyapunov_ready.connect(self.lyapunov_ready)

    def request_solve(self, config, values, ics, n, is_partial, t_max):
        self._solve_request.emit(config, values, ics, n, is_partial, t_max)

    def request_lyapunov(self, config, values):
        self._lyapunov_request.emit(config, values)

    def shutdown(self):
        self._solver_worker._cancel = True
        QtCore.QCoreApplication.removePostedEvents(self._solver_worker)
        self._solver_thread.quit()
        self._solver_thread.wait()
        self._lyapunov_worker._cancel = True
        QtCore.QCoreApplication.removePostedEvents(self._lyapunov_worker)
        self._lyapunov_thread.quit()
        self._lyapunov_thread.wait()
