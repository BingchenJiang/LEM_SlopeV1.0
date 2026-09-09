# -*- coding: utf-8 -*-
"""
动态降雨时序与入渗湿润锋演化模块
"""
from typing import List, Tuple
import numpy as np


class RainfallTimeSeries:
    """动态时序降雨过程线模型"""
    def __init__(
        self,
        time_series: List[Tuple[float, float]],  # [(时间 h, 降雨强度 mm/h)]
        ks_mm_h: float = 15.0,                  # 土体饱和渗透系数 (mm/h)
        delta_theta: float = 0.20               # 初始含水率到饱和含水率的容积差
    ):
        sorted_series = sorted(time_series, key=lambda x: x[0])
        self.times = np.array([p[0] for p in sorted_series], dtype=float)
        self.intensities = np.array([p[1] for p in sorted_series], dtype=float)
        self.ks = ks_mm_h
        self.delta_theta = max(0.05, delta_theta)

    def get_max_time(self) -> float:
        """获取降雨总历时"""
        return float(self.times[-1]) if len(self.times) > 0 else 0.0

    def get_intensity_at(self, t: float) -> float:
        """获取指定时刻的降雨强度 (mm/h)"""
        if len(self.times) == 0:
            return 0.0
        return float(np.interp(t, self.times, self.intensities))

    def get_wetting_front_depth(self, current_time: float) -> float:
        """
        计算从 t=0 到当前时刻 current_time 的入渗湿润锋推进深度 (米, m)
        采用时步积分解：
        I_inf(t) = min(Rainfall_Intensity(t), Ks)
        Delta_Z = (I_inf * Delta_t) / Delta_Theta
        """
        if current_time <= 0.0 or len(self.times) == 0:
            return 0.0

        eval_times = np.linspace(0.0, current_time, max(10, int(current_time * 4) + 1))
        dt = eval_times[1] - eval_times[0]
        cumulative_infil_mm = 0.0

        for t in eval_times:
            rain_i = self.get_intensity_at(t)
            infil_rate = min(rain_i, self.ks)
            cumulative_infil_mm += infil_rate * dt

        depth_m = (cumulative_infil_mm / 1000.0) / self.delta_theta
        return float(depth_m)