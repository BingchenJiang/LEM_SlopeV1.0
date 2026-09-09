# -*- coding: utf-8 -*-
"""
临界最危险滑面搜索算法基类与接口定义
"""
from abc import ABC, abstractmethod
from typing import Tuple, List, Optional, Callable
import numpy as np
from core.geometry import SlopeGeometry
from core.materials import SoilMaterial
from core.slicing import create_slices
from core.solvers.bishop import BishopSolver
from core.solvers.fellenius import FelleniusSolver


class BaseSlipSearcher(ABC):
    """滑面寻优算法基类"""
    def __init__(
        self,
        geom: SlopeGeometry,
        material: SoilMaterial,
        bounds: List[Tuple[float, float]],  # [(xmin, xmax), (ymin, ymax), (Rmin, Rmax)]
        eval_method: str = "Bishop",        # 寻优评估采用的条分法 (Bishop 或 Fellenius)
        ru: float = 0.0,
        use_water_table: bool = False,
        n_slices: int = 25
    ):
        self.geom = geom
        self.material = material
        self.bounds = bounds
        self.eval_method = eval_method
        self.ru = ru
        self.use_water_table = use_water_table
        self.n_slices = n_slices
        self.lb = np.array([b[0] for b in bounds], dtype=float)
        self.ub = np.array([b[1] for b in bounds], dtype=float)

    def evaluate(self, params: np.ndarray) -> float:
        """
        目标函数评估：计算指定 (xc, yc, R) 下的安全系数 Fs
        若未切入土体或不收敛，返回高额惩罚值 999.0
        """
        xc, yc, R = float(params[0]), float(params[1]), float(params[2])
        if R <= 0.1:
            return 999.0

        slices, info, _ = create_slices(
            self.geom, self.material, xc, yc, R,
            n_slices=self.n_slices, ru=self.ru, use_water_table=self.use_water_table
        )
        if not slices or not info:
            return 999.0

        x_edges = info[2]
        if self.eval_method == "Fellenius":
            solver = FelleniusSolver(slices, xc, yc, R, self.geom, x_edges)
        else:
            solver = BishopSolver(slices, xc, yc, R, self.geom, x_edges, tol=1e-4, max_iter=40)

        fs, _ = solver.solve()
        if fs is None or fs <= 0.05 or fs > 20.0:
            return 999.0
        return fs

    @abstractmethod
    def search(self, progress_callback: Optional[Callable[[int, int, float], None]] = None) -> Tuple[float, np.ndarray, str]:
        """
        执行寻优搜索
        返回: (最小安全系数 min_fs, 最优参数 [xc*, yc*, R*], 搜索详情日志)
        """
        pass