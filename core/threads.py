# -*- coding: utf-8 -*-
"""
基于 QThread 的后台异步寻优工作线程
确保大规模迭代计算期间图形界面响应流畅
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
    progress_updated = pyqtSignal(int, int, float)      # 当前步, 总步数, 当前最优Fs
    search_finished = pyqtSignal(float, list, str)      # 最优Fs, 最优参数[xc, yc, R], 说明信息
    search_failed = pyqtSignal(str)                     # 错误或终止信息

    def __init__(
        self,
        algo_name: str,
        eval_name: str,
        geom: SlopeGeometry,
        material: SoilMaterial,
        bounds: List[Tuple[float, float]],
        ru: float = 0.0,
        use_water_table: bool = False,
        parent=None
    ):
        super().__init__(parent)
        self.algo_name = algo_name
        self.eval_name = eval_name
        self.geom = geom
        self.material = material
        self.bounds = bounds
        self.ru = ru
        self.use_water_table = use_water_table
        self._is_interrupted = False

    def stop(self):
        """请求中断计算"""
        self._is_interrupted = True

    def run(self):
        try:
            if "PSO" in self.algo_name:
                searcher = PSOSearcher(
                    self.geom, self.material, self.bounds,
                    eval_method=self.eval_name, ru=self.ru,
                    use_water_table=self.use_water_table,
                    n_particles=25, max_iter=30
                )
            elif "退火" in self.algo_name:
                searcher = SimulatedAnnealingSearcher(
                    self.geom, self.material, self.bounds,
                    eval_method=self.eval_name, ru=self.ru,
                    use_water_table=self.use_water_table,
                    cooling_rate=0.90
                )
            elif "差分进化" in self.algo_name:
                searcher = DifferentialEvolutionSearcher(
                    self.geom, self.material, self.bounds,
                    eval_method=self.eval_name, ru=self.ru,
                    use_water_table=self.use_water_table,
                    popsize=10, maxiter=20
                )
            elif "单纯形" in self.algo_name:
                searcher = NelderMeadSearcher(
                    self.geom, self.material, self.bounds,
                    eval_method=self.eval_name, ru=self.ru,
                    use_water_table=self.use_water_table
                )
            else:
                searcher = GridSearcher(
                    self.geom, self.material, self.bounds,
                    eval_method=self.eval_name, ru=self.ru,
                    use_water_table=self.use_water_table,
                    nx=10, ny=10, nr=8
                )

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