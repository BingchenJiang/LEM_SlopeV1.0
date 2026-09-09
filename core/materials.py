# -*- coding: utf-8 -*-
"""
土体材料与抗剪强度本构模型模块
"""
import numpy as np


class SoilMaterial:
    """土体物理力学参数与有效应力莫尔-库仑本构模型"""
    def __init__(self, name: str = "默认土层", gamma: float = 20.0, c: float = 15.0, phi_deg: float = 20.0):
        self.name = name
        self.gamma = gamma                    # 天然重度 γ (kN/m³)
        self.c = c                            # 有效黏聚力 c' (kPa)
        self.phi_deg = phi_deg                # 有效内摩擦角 φ' (度)
        self.phi = np.radians(phi_deg)        # 内摩擦角 (弧度)

    def shear_strength(self, sigma_n: float, u: float = 0.0) -> float:
        """根据有效应力莫尔-库仑准则计算抗剪强度 τ_f = c' + (σ_n - u) * tan(φ')"""
        sigma_eff = max(0.0, sigma_n - u)
        return self.c + sigma_eff * np.tan(self.phi)