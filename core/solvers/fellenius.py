# -*- coding: utf-8 -*-
"""
瑞典条分法 (Fellenius / Ordinary / Swedish Circle Method)
力学假定：忽略土条间的一切作用力 (E_i = X_i = 0)，仅满足滑动体整体绕圆心的力矩平衡。
"""
import numpy as np
from typing import Tuple, Optional
from core.solvers.base import BaseLEMSolver


class FelleniusSolver(BaseLEMSolver):
    def solve(self) -> Tuple[Optional[float], str]:
        # 滑动力矩驱动项
        driving = sum(s.W * np.sin(s.alpha) for s in self.slices)
        if driving <= 0:
            return None, "下滑滑动力矩 <= 0（边坡自然稳定）"

        # 考虑孔隙水压折减有效法向力的抗滑阻力项
        resisting = sum(
            s.c * s.l + (s.W * np.cos(s.alpha) - s.u * s.l) * np.tan(s.phi)
            for s in self.slices
        )

        fs = resisting / driving
        return fs, "单步显式解析解（忽略条间力）"