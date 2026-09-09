# -*- coding: utf-8 -*-
"""
简化毕肖普法 (Simplified Bishop Method)
力学假定：考虑水平条间力，忽略条间剪力 (X_i = 0)，严格满足单条竖向力平衡与整体力矩平衡。
采用定点迭代法求解关于安全系数 Fs 的非线性隐式方程。
"""
import numpy as np
from typing import Tuple, Optional
from core.solvers.base import BaseLEMSolver


class BishopSolver(BaseLEMSolver):
    def solve(self) -> Tuple[Optional[float], str]:
        driving = sum(s.W * np.sin(s.alpha) for s in self.slices)
        if driving <= 0:
            return None, "下滑滑动力矩 <= 0"

        fs = 1.2  # 迭代初值
        for it in range(self.max_iter):
            num = 0.0
            for s in self.slices:
                m_alpha = np.cos(s.alpha) * (1.0 + np.tan(s.alpha) * np.tan(s.phi) / fs)
                if abs(m_alpha) < 1e-5:
                    m_alpha = 1e-5
                num += (s.c * s.b + (s.W - s.u * s.b) * np.tan(s.phi)) / m_alpha

            new_fs = num / driving
            if abs(new_fs - fs) < self.tol:
                return new_fs, f"收敛于第 {it + 1} 次定点迭代"
            fs = new_fs

        return fs, f"达到设定最大迭代步数 ({self.max_iter})"