# -*- coding: utf-8 -*-
"""
土体材料与抗剪强度本构模型模块
支持常规有效应力准则（饱和/天然工况）与 Fredlund 双应力非饱和土吸力本构
"""
import numpy as np


class SoilMaterial:
    """土体材料属性与抗剪强度准则"""
    def __init__(
        self,
        name: str = "默认土层",
        gamma_dry: float = 19.0,        # 天然/干重度 (kN/m3)
        gamma_sat: float = 21.0,        # 饱和重度 (kN/m3)
        c_prime: float = 15.0,          # 有效黏聚力 c' (kPa)
        phi_deg: float = 20.0,          # 有效内摩擦角 phi' (度)
        is_unsaturated: bool = False,   # 是否启用非饱和基质吸力强度贡献
        phi_b_deg: float = 15.0,        # 吸力摩擦角 phi^b (度)
        suction_cutoff: float = 100.0   # 最大吸力截断上限 (kPa)
    ):
        self.name = name
        self.gamma_dry = gamma_dry
        self.gamma_sat = gamma_sat
        self.c_prime = c_prime
        self.phi_deg = phi_deg
        self.phi = np.radians(phi_deg)
        self.is_unsaturated = is_unsaturated
        self.phi_b_deg = phi_b_deg
        self.phi_b = np.radians(phi_b_deg)
        self.suction_cutoff = suction_cutoff

    def get_apparent_cohesion(self, suction: float) -> float:
        """
        计算综合黏聚力
        1. 常规饱和/有效应力工况：不考虑负孔压贡献，严格返回 c'
        2. 非饱和吸力工况：根据 Fredlund 双应力理论引入基质吸力表观黏聚力增量
        """
        if not self.is_unsaturated or suction <= 0.0:
            return self.c_prime
        effective_suction = min(suction, self.suction_cutoff)
        return self.c_prime + effective_suction * np.tan(self.phi_b)