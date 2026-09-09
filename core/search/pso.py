# -*- coding: utf-8 -*-
"""
粒子群优化算法 (Particle Swarm Optimization, PSO)
高等土力学中广泛用于边坡临界滑面全局寻优，具备较强的全局勘探与跳出局部极值能力
"""
from typing import Tuple, Optional, Callable
import numpy as np
from core.search.base import BaseSlipSearcher


class PSOSearcher(BaseSlipSearcher):
    """粒子群滑面寻优求解器"""
    def __init__(self, *args, n_particles: int = 25, max_iter: int = 30, w: float = 0.7, c1: float = 1.5, c2: float = 1.5, **kwargs):
        super().__init__(*args, **kwargs)
        self.n_particles = n_particles
        self.max_iter = max_iter
        self.w = w    # 惯性权重
        self.c1 = c1  # 个体认知学习因子
        self.c2 = c2  # 社会群体学习因子

    def search(self, progress_callback: Optional[Callable[[int, int, float], None]] = None) -> Tuple[float, np.ndarray, str]:
        dim = len(self.bounds)
        pos = np.random.uniform(self.lb, self.ub, (self.n_particles, dim))
        vel = np.random.uniform(-(self.ub - self.lb) * 0.1, (self.ub - self.lb) * 0.1, (self.n_particles, dim))

        p_best_pos = np.copy(pos)
        p_best_val = np.array([self.evaluate(p) for p in pos])

        g_best_idx = int(np.argmin(p_best_val))
        g_best_pos = np.copy(p_best_pos[g_best_idx])
        g_best_val = float(p_best_val[g_best_idx])

        for it in range(self.max_iter):
            r1 = np.random.rand(self.n_particles, dim)
            r2 = np.random.rand(self.n_particles, dim)
            vel = self.w * vel + self.c1 * r1 * (p_best_pos - pos) + self.c2 * r2 * (g_best_pos - pos)
            pos = np.clip(pos + vel, self.lb, self.ub)

            for i in range(self.n_particles):
                val = self.evaluate(pos[i])
                if val < p_best_val[i]:
                    p_best_val[i] = val
                    p_best_pos[i] = np.copy(pos[i])
                    if val < g_best_val:
                        g_best_val = val
                        g_best_pos = np.copy(pos[i])

            if progress_callback:
                progress_callback(it + 1, self.max_iter, g_best_val)

        return g_best_val, g_best_pos, f"PSO 完成 {self.max_iter} 代迭代寻优 (粒子数: {self.n_particles})"