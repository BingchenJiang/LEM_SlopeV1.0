# -*- coding: utf-8 -*-
"""
土条离散剖分与微元几何/力学参数计算模块
"""
import numpy as np
from typing import List, Tuple, Optional
from core.geometry import SlopeGeometry
from core.materials import SoilMaterial


class Slice:
    """单个竖直土条的微元物理量"""
    def __init__(
        self,
        index: int,
        xm: float,
        b: float,
        h: float,
        y_top: float,
        y_base: float,
        alpha: float,
        l: float,
        W: float,
        u: float,
        material: SoilMaterial
    ):
        self.index = index            # 土条编号 (1 ~ N)
        self.xm = xm                  # 条块中点水平 X 坐标 (m)
        self.b = b                    # 条块宽度 (m)
        self.h = h                    # 条块平均高度 (m)
        self.y_top = y_top            # 顶部地表高程 (m)
        self.y_base = y_base          # 底部滑面高程 (m)
        self.alpha = alpha            # 底边倾角 (弧度)
        self.l = l                    # 底边滑面斜长 (m)
        self.W = W                    # 土条总重 (kN)
        self.u = u                    # 底面孔隙水压力 (kPa)
        self.material = material      # 关联土层材料
        self.c = material.c           # 黏聚力 (kPa)
        self.phi = material.phi       # 内摩擦角 (rad)


def create_slices(
    geom: SlopeGeometry,
    material: SoilMaterial,
    xc: float,
    yc: float,
    R: float,
    n_slices: int = 30,
    ru: float = 0.0,
    use_water_table: bool = False
) -> Tuple[Optional[List[Slice]], Optional[Tuple[float, float, np.ndarray]], str]:
    """对滑动土体进行等距竖向条分剖分"""
    inter = geom.intersect_circle(xc, yc, R)
    if not inter:
        return None, None, "滑弧未在边坡内部切出有效滑动体，请调整圆心或半径。"
        
    x_start, x_end = inter
    x_edges = np.linspace(x_start, x_end, n_slices + 1)
    slices: List[Slice] = []

    for i in range(n_slices):
        xl, xr = x_edges[i], x_edges[i + 1]
        xm = 0.5 * (xl + xr)
        b = xr - xl
        y_top = geom.get_ground_elevation(xm)
        y_base = float(yc - np.sqrt(max(0, R**2 - (xm - xc)**2)))
        h = max(0.001, y_top - y_base)

        # 坡面向右下滑的工程符号约定：位于圆心左侧的土条自重对滑面产生正向驱动力
        sin_alpha = np.clip((xc - xm) / R, -0.9999, 0.9999)
        alpha = float(np.arcsin(sin_alpha))
        l = b / max(1e-4, np.cos(alpha))
        W = material.gamma * b * h

        # 计算底边孔隙水压力
        if use_water_table and geom.wx is not None:
            yw = geom.get_water_elevation(xm)
            hw = max(0.0, (yw if yw is not None else y_base) - y_base)
            u = 9.81 * hw
        else:
            u = ru * material.gamma * h

        slices.append(Slice(i + 1, xm, b, h, y_top, y_base, alpha, l, W, u, material))

    return slices, (x_start, x_end, x_edges), "条分剖分计算成功"