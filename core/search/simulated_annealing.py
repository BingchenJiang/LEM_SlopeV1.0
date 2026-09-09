# -*- coding: utf-8 -*-
"""
模拟退火算法 (Simulated Annealing, SA)
基于物理退火 Metropolis 准则，以一定概率接受劣解，避免在多层土边坡滑面搜索中陷入局部死循环
"""
from typing import Tuple, Optional, Callable
import numpy as np
from core.search.base import BaseSlipSearcher


class SimulatedAnnealingSearcher(BaseSlipSearcher):
    """模拟退火滑面寻优求解器"""
    def __init__(self, *args, t_start: float = 100.0, t_end: float = 0.05, cooling_rate: float = 0.90, steps_per_t: int = 5, **kwargs):
        super().__init__(*args, **kwargs)
        self.t_start = t_start
        self.t_end = t_end
        self.cooling_rate = cooling_rate
        self.steps_per_t = steps_per_t

    def search(self, progress_callback: Optional[Callable[[int, int, float], None]] = None) -> Tuple[float, np.ndarray, str]:
        curr_x = (self.lb + self.ub) * 0.5
        curr_val = self.evaluate(curr_x)
        
        # 初始点有效性筛查
        for _ in range(50):
            if curr_val < 500.0:
                break
            curr_x = np.random.uniform(self.lb, self.ub)
            curr_val = self.evaluate(curr_x)

        best_x = np.copy(curr_x)
        best_val = curr_val

        T = self.t_start
        total_steps = int(np.ceil(np.log(self.t_end / self.t_start) / np.log(self.cooling_rate)))
        step_cnt = 0

        while T > self.t_end:
            for _ in range(self.steps_per_t):
                # 高斯摄动生成邻域候选解
                perturb = np.random.normal(0, (self.ub - self.lb) * 0.05)
                candidate_x = np.clip(curr_x + perturb, self.lb, self.ub)
                candidate_val = self.evaluate(candidate_x)

                delta = candidate_val - curr_val
                # Metropolis 准则
                if delta < 0 or np.random.rand() < np.exp(-delta / max(1e-6, T)):
                    curr_x = candidate_x
                    curr_val = candidate_val
                    if curr_val < best_val:
                        best_val = curr_val
                        best_x = np.copy(curr_x)

            T *= self.cooling_rate
            step_cnt += 1
            if progress_callback:
                progress_callback(step_cnt, total_steps, best_val)

        return best_val, best_x, f"模拟退火降温完成 (初温: {self.t_start}, 终温: {self.t_end}, 降温率: {self.cooling_rate})"