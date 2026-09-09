# -*- coding: utf-8 -*-
"""
土条离散剖分器模块
支持多层地层自重积分、降雨入渗湿润锋、非饱和基质吸力表观黏聚力、坡顶超载与地震拟静力荷载
"""
import numpy as np
from typing import List, Tuple, Optional
from core.geometry import SlopeGeometry
from core.materials import SoilMaterial


class Slice:
    """单个竖直切片土条的综合力学与几何微元对象"""
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
        q_load: float,
        kh: float,
        u: float,
        suction: float,
        c_total: float,
        phi: float,
        layer_name: str
    ):
        self.index = index
        self.xm = xm
        self.b = b
        self.h = h
        self.y_top = y_top
        self.y_base = y_base
        self.alpha = alpha
        self.l = l
        self.W_soil = W
        self.q_load = q_load
        self.W = W + q_load
        self.kh = kh
        self.Fh = kh * W
        self.u = u
        self.suction = suction
        self.c = c_total
        self.phi = phi
        self.layer_name = layer_name


def create_slices(
    geom: SlopeGeometry,
    materials: List[SoilMaterial],
    xc: float,
    yc: float,
    R: float,
    n_slices: int = 30,
    rainfall_depth: float = 0.0,
    kh: float = 0.0
) -> Tuple[Optional[List[Slice]], Optional[Tuple[float, float, np.ndarray]], str]:
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

        sin_alpha = np.clip((xc - xm) / R, -0.9999, 0.9999)
        alpha = float(np.arcsin(sin_alpha))
        l = b / max(1e-4, np.cos(alpha))

        # 判定浸润线与降雨湿润锋位置
        yw = geom.get_water_elevation(xm)
        wetting_front_y = y_top - max(0.0, rainfall_depth)

        # 多层地层竖向分段自重积分
        strata_y = geom.get_strata_elevations(xm)
        div_points = [y_top]
        for sy in strata_y:
            if y_base < sy < y_top:
                div_points.append(sy)
        div_points.append(y_base)
        div_points = sorted(div_points, reverse=True)

        W_soil = 0.0
        for seg_idx in range(len(div_points) - 1):
            y_high = div_points[seg_idx]
            y_low = div_points[seg_idx + 1]
            seg_h = y_high - y_low
            seg_mid_y = 0.5 * (y_high + y_low)

            layer_idx = geom.get_layer_index_at(xm, seg_mid_y)
            layer_idx = min(layer_idx, len(materials) - 1)
            mat = materials[layer_idx]

            # 饱和状态判定
            is_saturated = False
            if yw is not None and seg_mid_y <= yw:
                is_saturated = True
            elif seg_mid_y >= wetting_front_y and rainfall_depth > 0.0:
                is_saturated = True

            use_gamma = mat.gamma_sat if is_saturated else mat.gamma_dry
            W_soil += use_gamma * b * seg_h

        # 坡顶附加外荷载
        q_val = geom.get_surcharge_at(xm)
        q_load = q_val * b

        # 底面孔压与基质吸力
        if yw is not None:
            if y_base <= yw:
                u = 9.81 * (yw - y_base)
                suction = 0.0
            else:
                u = 0.0
                suction = 9.81 * (y_base - yw)
        else:
            u = 0.0
            suction = 0.0

        # 若降雨湿润锋穿透至滑面，基质吸力完全消散归零
        if y_base >= wetting_front_y and rainfall_depth > 0.0:
            suction = 0.0

        # 底面所属地层材料与表观黏聚力提取
        base_layer_idx = geom.get_layer_index_at(xm, y_base)
        base_layer_idx = min(base_layer_idx, len(materials) - 1)
        base_mat = materials[base_layer_idx]

        c_total = base_mat.get_apparent_cohesion(suction)
        phi = base_mat.phi

        slices.append(Slice(
            index=i + 1,
            xm=xm,
            b=b,
            h=h,
            y_top=y_top,
            y_base=y_base,
            alpha=alpha,
            l=l,
            W=W_soil,
            q_load=q_load,
            kh=kh,
            u=u,
            suction=suction,
            c_total=c_total,
            phi=phi,
            layer_name=base_mat.name
        ))

    return slices, (x_start, x_end, x_edges), "多层地层与水力切片成功"