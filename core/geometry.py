# -*- coding: utf-8 -*-
"""
边坡几何外轮廓、多层地层分界面、地下水位线与外荷载拓扑模块
"""
import numpy as np
from typing import List, Tuple, Optional


class SlopeGeometry:
    """边坡几何多段线与多层地层拓扑管理器"""
    def __init__(
        self,
        ground_coords: List[Tuple[float, float]],
        water_coords: Optional[List[Tuple[float, float]]] = None,
        strata_boundaries: Optional[List[List[Tuple[float, float]]]] = None,
        surcharge_loads: Optional[List[Tuple[float, float, float]]] = None
    ):
        sorted_ground = sorted(ground_coords, key=lambda p: p[0])
        self.gx = np.array([p[0] for p in sorted_ground], dtype=float)
        self.gy = np.array([p[1] for p in sorted_ground], dtype=float)

        if water_coords and len(water_coords) >= 2:
            sorted_water = sorted(water_coords, key=lambda p: p[0])
            self.wx = np.array([p[0] for p in sorted_water], dtype=float)
            self.wy = np.array([p[1] for p in sorted_water], dtype=float)
        else:
            self.wx, self.wy = None, None

        self.strata_lines = []
        if strata_boundaries:
            for sb in strata_boundaries:
                if len(sb) >= 2:
                    sorted_sb = sorted(sb, key=lambda p: p[0])
                    bx = np.array([p[0] for p in sorted_sb], dtype=float)
                    by = np.array([p[1] for p in sorted_sb], dtype=float)
                    self.strata_lines.append((bx, by))

        self.surcharge_loads = surcharge_loads if surcharge_loads else []

    def get_ground_elevation(self, x: float) -> float:
        return float(np.interp(x, self.gx, self.gy))

    def get_water_elevation(self, x: float) -> Optional[float]:
        if self.wx is not None:
            return float(np.interp(x, self.wx, self.wy))
        return None

    def get_strata_elevations(self, x: float) -> List[float]:
        return [float(np.interp(x, bx, by)) for bx, by in self.strata_lines]

    def get_layer_index_at(self, x: float, y: float) -> int:
        if not self.strata_lines:
            return 0
        elevs = self.get_strata_elevations(x)
        for idx, elev in enumerate(elevs):
            if y >= elev:
                return idx
        return len(elevs)

    def get_surcharge_at(self, x: float) -> float:
        total_q = 0.0
        for x1, x2, q in self.surcharge_loads:
            if min(x1, x2) <= x <= max(x1, x2):
                total_q += q
        return total_q

    def intersect_circle(self, xc: float, yc: float, R: float) -> Optional[Tuple[float, float]]:
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