# -*- coding: utf-8 -*-
"""
经典网格搜索法 (Fellenius Grid Search)
工程界工业软件 (如 SLOPE/W, Slide2) 的基准扫描算法，离散扫描空间矩阵与半径
"""
from typing import Tuple, Optional, Callable
import numpy as np
from core.search.base import BaseSlipSearcher


class GridSearcher(BaseSlipSearcher):
    """网格离散扫描滑面求解器"""
    def __init__(self, *args, nx: int = 10, ny: int = 10, nr: int = 8, **kwargs):
        super().__init__(*args, **kwargs)
        self.nx = nx
        self.ny = ny
        self.nr = nr

    def search(self, progress_callback: Optional[Callable[[int, int, float], None]] = None) -> Tuple[float, np.ndarray, str]:
        xs = np.linspace(self.bounds[0][0], self.bounds[0][1], self.nx)
        ys = np.linspace(self.bounds[1][0], self.bounds[1][1], self.ny)
        rs = np.linspace(self.bounds[2][0], self.bounds[2][1], self.nr)

        total_trials = self.nx * self.ny * self.nr
        best_fs = 999.0
        best_params = np.array([xs[0], ys[0], rs[0]])
        cnt = 0

        for x in xs:
            for y in ys:
                for r in rs:
                    cnt += 1
                    val = self.evaluate(np.array([x, y, r]))
                    if val < best_fs:
                        best_fs = val
                        best_params = np.array([x, y, r])
                    if progress_callback and cnt % 50 == 0:
                        progress_callback(cnt, total_trials, best_fs)

        return best_fs, best_params, f"网格搜索扫描完成 (总计离散试算点: {total_trials})"