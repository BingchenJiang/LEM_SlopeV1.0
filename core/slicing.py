# -*- coding: utf-8 -*-
"""
土条离散剖分器模块
支持多层地层自重积分、降雨入渗湿润锋、非饱和基质吸力表观黏聚力、坡顶超载与地震拟静力荷载
"""
import numpy as np
from typing import List, Tuple, Optional
from core.geometry import SlopeGeometry
from core.materials import SoilMaterial
from core.slip_surface import BaseSlipSurface, CircularSlipSurface


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
        layer_name: str,
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
    xc=None,                              # 兼容旧接口：可以是数字(Xc) 也可以是 BaseSlipSurface
    yc: Optional[float] = None,
    R: Optional[float] = None,
    n_slices: int = 30,
    rainfall_depth: float = 0.0,
    kh: float = 0.0,
    slip_surface: Optional[BaseSlipSurface] = None,
    tension_crack=None,
    anchors=None,
    **kwargs,                             # 仅为兼容旧接口，不推荐使用
) -> Tuple[Optional[List[Slice]], Optional[Tuple[float, float, np.ndarray]], str]:
    """
    通用边坡切片剖分器（同时支持圆弧与非圆弧折线滑面）

    返回: (slices, (x_start, x_end, x_edges), message)
      - 成功: 第三项为 "切片剖分成功"
      - 失败: slices 与 info 均为 None, 第三项为具体原因
    """
    if n_slices < 1:
        return None, None, "切片数必须 ≥ 1"

    # ---------- 1. 统一提取滑面对象 ----------
    # 兼容：xc 位置传了一个滑面对象（旧接口）
    if isinstance(xc, BaseSlipSurface) and slip_surface is None:
        slip_surface = xc
        xc = None

    if slip_surface is None:
        if xc is None or yc is None or R is None:
            return None, None, "未指定滑面参数（需提供 slip_surface 或 xc/yc/R）"
        slip_surface = CircularSlipSurface(float(xc), float(yc), float(R))

    # ---------- 2. 求滑面与地表的水平跨越区间 ----------
    inter = slip_surface.get_x_range(geom.gx, geom.gy)
    if not inter:
        return None, None, "滑面未在边坡内部切出有效滑动体"

    x_start, x_end = inter
    if x_end - x_start < 1e-3:
        return None, None, f"滑面水平跨度太小: {x_end - x_start:.4f} m"

    x_edges = np.linspace(x_start, x_end, n_slices + 1)
    slices: List[Slice] = []

    # 允许的最小条底厚度（m），防止极端薄条造成数值爆炸
    MIN_THICKNESS = 1e-3

    for i in range(n_slices):
        xl, xr = float(x_edges[i]), float(x_edges[i + 1])
        xm = 0.5 * (xl + xr)
        b = xr - xl
        if b <= 0:
            return None, None, f"第 {i+1} 条宽度非法: b={b}"

        y_top = geom.get_ground_elevation(xm)

        # ---------- 3. 底高程与倾角 ----------
        y_base = slip_surface.get_y_base(xm)

        # 滑面穿出地面 → 整条滑面作废
        # 用极宽容差 -1e-6，只拦“真的冒头”，避免浮点误差误杀浅滑面
        if y_base >= y_top - 1e-6:
            return None, None, (
                f"滑面穿出地面: 第{i+1}条 xm={xm:.3f}, "
                f"y_base={y_base:.4f} >= y_top={y_top:.4f}"
            )

        h = max(MIN_THICKNESS, y_top - y_base)

        alpha = float(slip_surface.get_alpha(xm))
        # 折线滑面在折点附近 alpha 可能接近 ±π/2，这里钳制 cos 避免 l 爆炸
        cos_a = np.cos(alpha)
        if abs(cos_a) < 0.1:
            cos_a = 0.1 if cos_a >= 0 else -0.1
        l = b / cos_a

        # ---------- 4. 水位与湿润锋 ----------
        yw = geom.get_water_elevation(xm)
        wetting_front_y = y_top - max(0.0, float(rainfall_depth))

        # ---------- 5. 多层地层自重积分 ----------
        strata_y = geom.get_strata_elevations(xm)
        div_points = [y_top]
        for sy in strata_y:
            if y_base + 1e-9 < sy < y_top - 1e-9:
                div_points.append(float(sy))
        div_points.append(y_base)
        div_points = sorted(div_points, reverse=True)

        W_soil = 0.0
        for seg_idx in range(len(div_points) - 1):
            y_high, y_low = div_points[seg_idx], div_points[seg_idx + 1]
            seg_h = y_high - y_low
            if seg_h <= 1e-9:
                continue
            seg_mid_y = 0.5 * (y_high + y_low)

            layer_idx = min(geom.get_layer_index_at(xm, seg_mid_y), len(materials) - 1)
            mat = materials[layer_idx]

            is_saturated = (
                (yw is not None and seg_mid_y <= yw)
                or (rainfall_depth > 0.0 and seg_mid_y >= wetting_front_y)
            )
            use_gamma = mat.gamma_sat if is_saturated else mat.gamma_dry
            W_soil += use_gamma * b * seg_h

        # ---------- 6. 外载与孔隙水压力 ----------
        q_load = geom.get_surcharge_at(xm) * b

        if yw is not None:
            u = 9.81 * (yw - y_base) if y_base <= yw else 0.0
            suction = 9.81 * (y_base - yw) if y_base > yw else 0.0
        else:
            u, suction = 0.0, 0.0

        # 降雨湿润锋之下认为吸力已丧失
        if rainfall_depth > 0.0 and y_base >= wetting_front_y:
            suction = 0.0

        # ---------- 7. 条底力学参数 ----------
        base_layer_idx = min(geom.get_layer_index_at(xm, y_base), len(materials) - 1)
        base_mat = materials[base_layer_idx]

        s_obj = Slice(
            index=i + 1,
            xm=xm, b=b, h=h, y_top=y_top, y_base=y_base,
            alpha=alpha, l=l,
            W=W_soil, q_load=q_load, kh=kh,
            u=u, suction=suction,
            c_total=base_mat.get_apparent_cohesion(suction),
            phi=base_mat.phi,
            layer_name=base_mat.name,
        )
        s_obj.y_cg = 0.5 * (y_top + y_base)
        slices.append(s_obj)

    if not slices:
        return None, None, "切片列表为空"

    return slices, (x_start, x_end, x_edges), "切片剖分成功"