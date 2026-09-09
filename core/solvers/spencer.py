# -*- coding: utf-8 -*-
"""
斯宾塞法 (Spencer Method)
力学假定：完全平衡严密法，同时满足力平衡与整体力矩平衡。
假定所有条间力的倾角为同一常数 θ（即条间剪力与法向力之比恒定：X_i / E_i = tan(θ) = λ）。
通过牛顿法联立求解二维非线性方程组得到 (Fs, θ)。
"""
import numpy as np
from typing import Tuple, Optional
from scipy.optimize import root
from core.solvers.base import BaseLEMSolver
from core.solvers.bishop import BishopSolver


class SpencerSolver(BaseLEMSolver):
    def _evaluate_residuals(self, params: np.ndarray) -> list:
        F, lam = params
        if F <= 0.1:
            return [1e5, 1e5]

        E = 0.0  # 边界条件：坡顶外边缘条间推力 E_0 = 0
        resisting_moment = 0.0

        for s in self.slices:
            alpha = s.alpha
            tan_phi = np.tan(s.phi)
            S0 = (s.c * s.l - s.u * s.l * tan_phi) / F
            A = np.sin(alpha) - (tan_phi / F) * np.cos(alpha)
            B = np.cos(alpha) + (tan_phi / F) * np.sin(alpha)

            denom = B - A * lam
            if abs(denom) < 1e-6:
                denom = 1e-6 if denom >= 0 else -1e-6

            E_next = (E * (B - A * lam) + A * s.W - S0) / denom
            N = ((E_next - E) + S0 * np.cos(alpha)) / A if abs(A) > 1e-5 else s.W * np.cos(alpha)
            T = S0 + N * (tan_phi / F)
            resisting_moment += T * self.R
            E = E_next

        driving_moment = sum(s.W * self.R * np.sin(s.alpha) for s in self.slices)
        # 残差 1: 坡脚末端条间推力归零 (E_n = 0)
        # 残差 2: 整体力矩平衡残差归零
        return [E, resisting_moment - driving_moment]

    def solve(self) -> Tuple[Optional[float], str]:
        b_solver = BishopSolver(self.slices, self.xc, self.yc, self.R, self.geom, self.x_edges, self.tol)
        init_fs, _ = b_solver.solve()
        if init_fs is None:
            init_fs = 1.2

        sol = root(self._evaluate_residuals, [init_fs, 0.0], method='hybr', tol=self.tol)
        if sol.success and sol.x[0] > 0:
            fs = sol.x[0]
            theta_deg = float(np.degrees(np.arctan(sol.x[1])))
            return fs, f"完全平衡收敛: 条间力倾角 θ={theta_deg:.2f}° (λ={sol.x[1]:.4f})"

        return None, "非线性力与力矩联立方程未收敛"