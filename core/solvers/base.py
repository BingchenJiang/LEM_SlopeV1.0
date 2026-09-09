# -*- coding: utf-8 -*-
"""
极限平衡求解器抽象基类与接口规范
"""
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
import numpy as np
from core.slicing import Slice
from core.geometry import SlopeGeometry


class BaseLEMSolver(ABC):
    """极限平衡求解器基类"""
    def __init__(
        self,
        slices: List[Slice],
        xc: float,
        yc: float,
        R: float,
        geom: SlopeGeometry,
        x_edges: np.ndarray,
        tol: float = 1e-5,
        max_iter: int = 100
    ):
        self.slices = slices
        self.xc = xc
        self.yc = yc
        self.R = R
        self.geom = geom
        self.x_edges = x_edges
        self.tol = tol
        self.max_iter = max_iter

    @abstractmethod
    def solve(self) -> Tuple[Optional[float], str]:
        """
        求解安全系数核心抽象接口
        返回: (安全系数 Fs, 收敛状态说明)
        """
        pass