# -*- coding: utf-8 -*-
"""
摩根斯坦-普赖斯法 (Morgenstern-Price Method / GLE)
力学假定：广义极限平衡严密法，同时满足力平衡与整体力矩平衡。
假定条间剪力与法向力满足 X = λ * f(x) * E，其中 f(x) 采用标准半正弦波函数。
联立求解二维非线性方程组确定 (Fs, λ)。
"""
import numpy as np
from typing import Tuple, Optional
from scipy.optimize import root
from core.solvers.base import BaseLEMSolver
from core.solvers.bishop import BishopSolver


class MorgensternPriceSolver(BaseLEMSolver):
    def __init__(self, *args, interslice_func: str = "half_sine", **kwargs):
        super().__init__(*args, **kwargs)
        self.interslice_func = interslice_func

    def _get_fx(self, x: float) -> float:
        x_s, x_e = self.x_edges[0], self.x_edges[-1]
        rel = (x - x_s) / max(1e-4, x_e - x_s)
        if self.interslice_func == "half_sine":
            return float(np.sin(np.pi * np.clip(rel, 0.0, 1.0)))
        return 1.0

    def _evaluate_residuals(self, params: np.ndarray) -> list:
        F, lam = params
        if F <= 0.1:
            return [1e5, 1e5]

        E = 0.0
        resisting_moment = 0.0
        k_edges = [lam * self._get_fx(x) for x in self.x_edges]

        for i, s in enumerate(self.slices):
            alpha = s.alpha
            tan_phi = np.tan(s.phi)
            S0 = (s.c * s.l - s.u * s.l * tan_phi) / F
            A = np.sin(alpha) - (tan_phi / F) * np.cos(alpha)
            B = np.cos(alpha) + (tan_phi / F) * np.sin(alpha)

            k_l = k_edges[i]
            k_r = k_edges[i + 1]

            denom = B - A * k_r
            if abs(denom) < 1e-6:
                denom = 1e-6 if denom >= 0 else -1e-6

            E_next = (E * (B - A * k_l) + A * s.W - S0) / denom
            N = ((E_next - E) + S0 * np.cos(alpha)) / A if abs(A) > 1e-5 else s.W * np.cos(alpha)
            T = S0 + N * (tan_phi / F)
            resisting_moment += T * self.R
            E = E_next

        driving_moment = sum(s.W * self.R * np.sin(s.alpha) for s in self.slices)
        return [E, resisting_moment - driving_moment]

    def solve(self) -> Tuple[Optional[float], str]:
        b_solver = BishopSolver(self.slices, self.xc, self.yc, self.R, self.geom, self.x_edges, self.tol)
        init_fs, _ = b_solver.solve()
        if init_fs is None:
            init_fs = 1.2

        sol = root(self._evaluate_residuals, [init_fs, 0.0], method='hybr', tol=self.tol)
        if sol.success and sol.x[0] > 0:
            fs = sol.x[0]
            return fs, f"完全平衡收敛: 比例系数 λ={sol.x[1]:.4f} (条间函数: 半正弦波)"

        return None, "M-P 广义极限平衡方程未收敛"