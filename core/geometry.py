# -*- coding: utf-8 -*-
"""
边坡几何外轮廓、浸润线与滑面求交模块
"""
import numpy as np
from typing import List, Tuple, Optional


class SlopeGeometry:
    """边坡地表线、浸润线与滑弧几何拓扑管理器"""
    def __init__(self, ground_coords: List[Tuple[float, float]], water_coords: Optional[List[Tuple[float, float]]] = None):
        # 确保折线点严格按水平 X 坐标升序排列
        sorted_ground = sorted(ground_coords, key=lambda p: p[0])
        self.gx = np.array([p[0] for p in sorted_ground], dtype=float)
        self.gy = np.array([p[1] for p in sorted_ground], dtype=float)

        if water_coords:
            sorted_water = sorted(water_coords, key=lambda p: p[0])
            self.wx = np.array([p[0] for p in sorted_water], dtype=float)
            self.wy = np.array([p[1] for p in sorted_water], dtype=float)
        else:
            self.wx, self.wy = None, None

    def get_ground_elevation(self, x: float) -> float:
        """获取指定水平 X 坐标处的地表高程"""
        return float(np.interp(x, self.gx, self.gy))

    def get_water_elevation(self, x: float) -> Optional[float]:
        """获取指定水平 X 坐标处的地下水浸润线高程"""
        if self.wx is not None:
            return float(np.interp(x, self.wx, self.wy))
        return None

    def intersect_circle(self, xc: float, yc: float, R: float) -> Optional[Tuple[float, float]]:
        """计算试算圆弧与边坡地表的出入土交点 X 坐标 (x_start, x_end)"""
        xs = np.linspace(xc - R + 1e-5, xc + R - 1e-5, 2000)
        yc_circle = yc - np.sqrt(np.maximum(0, R**2 - (xs - xc)**2))
        yg = np.interp(xs, self.gx, self.gy)
        diff = yc_circle - yg
        inside = np.where(diff < 0)[0]
        
        if len(inside) < 2:
            return None
        x_start = float(xs[inside[0]])
        x_end = float(xs[inside[-1]])
        if x_end - x_start < 0.1:
            return None
        return x_start, x_end