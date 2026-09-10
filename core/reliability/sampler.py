# -*- coding: utf-8 -*-
"""
岩土参数概率分布与互相关随机抽样器
"""
from typing import Dict
import numpy as np


def sample_soil_parameters(
    n_samples: int,
    mean_c: float,
    cov_c: float,
    dist_c: str,
    mean_phi: float,
    cov_phi: float,
    dist_phi: str,
    rho_c_phi: float = -0.50,
    mean_gamma: float = 20.0,
    cov_gamma: float = 0.08
) -> Dict[str, np.ndarray]:
    """
    生成具有负相关关系的 c, phi 和重度 gamma 随机样本序列
    """
    # 1. 构造相关系数矩阵并进行 Cholesky 分解
    rho = float(np.clip(rho_c_phi, -0.95, 0.95))
    R_matrix = np.array([[1.0, rho], [rho, 1.0]], dtype=float)
    L = np.linalg.cholesky(R_matrix)

    # 2. 生成标准正态不相关随机变量，转换为相关标准正态变量
    z_raw = np.random.normal(0.0, 1.0, (n_samples, 2))
    z_corr = z_raw @ L.T
    z1 = z_corr[:, 0]   # 第 0 列对应黏聚力 c
    z2 = z_corr[:, 1]   # 第 1 列对应内摩擦角 phi

    # 3. 黏聚力 c 抽样 (默认对数正态分布)
    if "对数" in dist_c or "Log" in dist_c:
        cov_c_val = max(0.01, cov_c)
        zeta_c = np.sqrt(np.log(1.0 + cov_c_val**2))
        lambda_c = np.log(max(0.1, mean_c)) - 0.5 * zeta_c**2
        c_samples = np.exp(lambda_c + zeta_c * z1)
    else:
        std_c = mean_c * max(0.01, cov_c)
        c_samples = np.maximum(0.1, mean_c + std_c * z1)

    # 4. 内摩擦角 phi 抽样 (度)
    if "对数" in dist_phi or "Log" in dist_phi:
        cov_phi_val = max(0.01, cov_phi)
        zeta_phi = np.sqrt(np.log(1.0 + cov_phi_val**2))
        lambda_phi = np.log(max(1.0, mean_phi)) - 0.5 * zeta_phi**2
        phi_deg_samples = np.clip(np.exp(lambda_phi + zeta_phi * z2), 1.0, 50.0)
    else:
        std_phi = mean_phi * max(0.01, cov_phi)
        phi_deg_samples = np.clip(mean_phi + std_phi * z2, 1.0, 50.0)

    # 5. 重度 gamma 抽样 (正态分布，截断下限 10.0 kN/m3)
    std_gamma = mean_gamma * max(0.01, cov_gamma)
    gamma_samples = np.maximum(10.0, np.random.normal(mean_gamma, std_gamma, n_samples))

    return {
        "c": c_samples,
        "phi_deg": phi_deg_samples,
        "gamma": gamma_samples
    }