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
        materials: List[SoilMaterial],       # 注意此处改为复数 materials
        bounds: List[Tuple[float, float]],
        eval_method: str = "Bishop",
        rainfall_depth: float = 0.0,         # 接收降雨入渗深度
        kh: float = 0.0,                     # 接收地震力系数
        n_slices: int = 25
    ):
        self.geom = geom
        self.materials = materials
        self.bounds = bounds
        self.eval_method = eval_method
        self.rainfall_depth = rainfall_depth
        self.kh = kh
        self.n_slices = n_slices
        self.lb = np.array([b[0] for b in bounds], dtype=float)
        self.ub = np.array([b[1] for b in bounds], dtype=float)

    def evaluate(self, params: np.ndarray) -> float:
        """评估目标函数：计算指定 (xc, yc, R) 下的安全系数 Fs"""
        xc, yc, R = float(params[0]), float(params[1]), float(params[2])
        if R <= 0.1:
            return 999.0

        slices, info, _ = create_slices(
            self.geom,
            self.materials,
            xc,
            yc,
            R,
            n_slices=self.n_slices,
            rainfall_depth=self.rainfall_depth,
            kh=self.kh
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
        pass