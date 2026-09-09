# -*- coding: utf-8 -*-
"""
单纯形搜索法 (Nelder-Mead Simplex)
经典无梯度直接极值优化算法，适合已知粗略破坏区域后的高精度快速极小值收敛
"""
from typing import Tuple, Optional, Callable
import numpy as np
from scipy.optimize import minimize
from core.search.base import BaseSlipSearcher


class NelderMeadSearcher(BaseSlipSearcher):
    """单纯形局部滑面寻优求解器"""
    def __init__(self, *args, init_guess: Optional[np.ndarray] = None, maxiter: int = 150, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_guess = init_guess if init_guess is not None else (self.lb + self.ub) * 0.5
        self.maxiter = maxiter

    def search(self, progress_callback: Optional[Callable[[int, int, float], None]] = None) -> Tuple[float, np.ndarray, str]:
        it_cnt = [0]
        def callback_fn(xk):
            it_cnt[0] += 1
            if progress_callback:
                progress_callback(it_cnt[0], self.maxiter, self.evaluate(xk))

        res = minimize(
            self.evaluate,
            self.init_guess,
            method="Nelder-Mead",
            bounds=self.bounds,
            callback=callback_fn,
            options={"maxiter": self.maxiter, "xatol": 1e-3, "fatol": 1e-4}
        )

        return float(res.fun), res.x, f"Nelder-Mead 单纯形法收敛于第 {res.nit} 步迭代"