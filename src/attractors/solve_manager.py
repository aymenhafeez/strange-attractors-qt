from pyqtgraph.Qt import QtCore

from .worker import LyapunovWorker, SolveWorker


class SolveManager(QtCore.QObject):
    solutions_ready = QtCore.pyqtSignal(int, object, bool)
    lyapunov_ready = QtCore.pyqtSignal(int, object, float, object, object)
    _solve_request = QtCore.pyqtSignal(int, object, dict, list, int, bool, float)
    _lyapunov_request = QtCore.pyqtSignal(int, object, dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._solve_request_id = 0
        self._lyapunov_request_id = 0

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
        self._solve_request_id += 1
        request_id = self._solve_request_id
        self._solve_request.emit(request_id, config, values, ics, n, is_partial, t_max)
        return request_id

    def request_lyapunov(self, config, values):
        self._lyapunov_request_id += 1
        request_id = self._lyapunov_request_id
        self._lyapunov_request.emit(request_id, config, values)
        return request_id

    def cancel_solve(self):
        self._solver_worker._cancel = True
        QtCore.QCoreApplication.removePostedEvents(self._solver_worker)

    def cancel_lyapunov(self):
        self._lyapunov_worker._cancel = True
        QtCore.QCoreApplication.removePostedEvents(self._lyapunov_worker)

    def shutdown(self):
        self.cancel_solve()
        self._solver_thread.quit()
        self._solver_thread.wait()
        self.cancel_lyapunov()
        self._lyapunov_thread.quit()
        self._lyapunov_thread.wait()
