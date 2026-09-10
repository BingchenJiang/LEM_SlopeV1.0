# -*- coding: utf-8 -*-
"""
基于 QThread 的后台异步寻优计算工作线程
保证多层土、水力与复杂荷载条件下的全局迭代计算期间 GUI 界面平滑响应
"""
from PyQt5.QtCore import QThread, pyqtSignal
from typing import List, Tuple
from core.geometry import SlopeGeometry
from core.materials import SoilMaterial
from core.search import (
    PSOSearcher, SimulatedAnnealingSearcher,
    DifferentialEvolutionSearcher, NelderMeadSearcher, GridSearcher
)


class OptimizationWorker(QThread):
    """全局优化搜索异步工作线程"""
    progress_updated = pyqtSignal(int, int, float)
    search_finished = pyqtSignal(float, list, str)
    search_failed = pyqtSignal(str)

    def __init__(
        self,
        algo_name: str,
        eval_name: str,
        geom: SlopeGeometry,
        materials: List[SoilMaterial],
        bounds: List[Tuple[float, float]],
        rainfall_depth: float = 0.0,
        kh: float = 0.0,
        parent=None
    ):
        super().__init__(parent)
        self.algo_name = algo_name
        self.eval_name = eval_name
        self.geom = geom
        self.materials = materials
        self.bounds = bounds
        self.rainfall_depth = rainfall_depth
        self.kh = kh
        self._is_interrupted = False

    def stop(self):
        self._is_interrupted = True

    def run(self):
        try:
            kwargs = {
                "geom": self.geom,
                "materials": self.materials,
                "bounds": self.bounds,
                "eval_method": self.eval_name,
                "rainfall_depth": self.rainfall_depth,
                "kh": self.kh
            }

            if "PSO" in self.algo_name:
                searcher = PSOSearcher(**kwargs, n_particles=25, max_iter=30)
            elif "退火" in self.algo_name:
                searcher = SimulatedAnnealingSearcher(**kwargs, cooling_rate=0.90)
            elif "差分进化" in self.algo_name:
                searcher = DifferentialEvolutionSearcher(**kwargs, popsize=10, maxiter=20)
            elif "单纯形" in self.algo_name:
                searcher = NelderMeadSearcher(**kwargs)
            else:
                searcher = GridSearcher(**kwargs, nx=10, ny=10, nr=8)

            def callback_fn(current, total, current_best):
                if not self._is_interrupted:
                    self.progress_updated.emit(current, total, current_best)

            best_fs, best_params, info_msg = searcher.search(progress_callback=callback_fn)

            if not self._is_interrupted:
                self.search_finished.emit(float(best_fs), [float(p) for p in best_params], str(info_msg))
            else:
                self.search_failed.emit("用户已主动终止搜索计算。")
        except Exception as e:
            self.search_failed.emit(f"寻优计算发生异常: {str(e)}")
            

class ReliabilityWorker(QThread):
    """边坡可靠度与失效概率评估后台异步工作线程"""
    progress_updated = pyqtSignal(int, int, float)  # current, total, current_pf
    reliability_finished = pyqtSignal(dict)         # 结果字典
    reliability_failed = pyqtSignal(str)            # 错误信息

    def __init__(self, simulator, parent=None):
        super().__init__(parent)
        self.simulator = simulator
        self._is_interrupted = False

    def stop(self):
        """用户点击终止评价"""
        self._is_interrupted = True

    def run(self):
        try:
            def callback_fn(current, total, current_pf):
                if not self._is_interrupted:
                    self.progress_updated.emit(current, total, current_pf)

            def is_interrupted():
                return self._is_interrupted

            res = self.simulator.run(
                progress_callback=callback_fn,
                is_interrupted_fn=is_interrupted
            )

            if self._is_interrupted:
                self.reliability_failed.emit("用户已主动终止蒙特卡洛抽样计算。")
            elif not res.get("success", False):
                self.reliability_failed.emit(res.get("error", "抽样计算未收敛。"))
            else:
                self.reliability_finished.emit(res)
        except Exception as e:
            self.reliability_failed.emit(f"可靠度计算发生异常: {str(e)}")