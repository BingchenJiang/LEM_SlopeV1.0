# -*- coding: utf-8 -*-
"""
差分进化算法 (Differential Evolution, DE)
基于种群向量差分变异的高效全局演化算法
"""
from typing import Tuple, Optional, Callable
import numpy as np
from scipy.optimize import differential_evolution
from core.search.base import BaseSlipSearcher


class DifferentialEvolutionSearcher(BaseSlipSearcher):
    """差分进化滑面寻优求解器"""
    def __init__(self, *args, popsize: int = 12, maxiter: int = 25, **kwargs):
        super().__init__(*args, **kwargs)
        self.popsize = popsize
        self.maxiter = maxiter

    def search(self, progress_callback: Optional[Callable[[int, int, float], None]] = None) -> Tuple[float, np.ndarray, str]:
        iter_counter = [0]

        def callback_fn(xk, convergence):
            iter_counter[0] += 1
            if progress_callback:
                val = self.evaluate(xk)
                progress_callback(iter_counter[0], self.maxiter, val)

        res = differential_evolution(
            self.evaluate,
            self.bounds,
            popsize=self.popsize,
            maxiter=self.maxiter,
            mutation=(0.5, 1.0),
            recombination=0.7,
            callback=callback_fn,
            seed=42
        )

        return float(res.fun), res.x, f"差分进化寻优完成 (种群规模: {self.popsize}, 迭代代数: {res.nit})"