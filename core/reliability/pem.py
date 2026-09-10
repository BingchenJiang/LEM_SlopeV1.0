# -*- coding: utf-8 -*-
"""
Rosenblueth 点估计法 (Point Estimate Method, PEM) 边坡可靠度快速核算
"""
from typing import List, Dict, Any
import numpy as np
from scipy.stats import norm

from core.geometry import SlopeGeometry
from core.materials import SoilMaterial
from core.slicing import create_slices
from core.solvers.bishop import BishopSolver


def run_point_estimate_analysis(
    geom: SlopeGeometry,
    materials: List[SoilMaterial],
    xc: float,
    yc: float,
    R: float,
    cov_c: float = 0.25,
    cov_phi: float = 0.15,
    rho_c_phi: float = -0.50,
    rainfall_depth: float = 0.0,
    kh: float = 0.0
) -> Dict[str, Any]:
    """
    通过 2^2=4 个特征点评估安全系数均值与方差
    """
    mat = materials[0]
    mu_c = mat.c_prime
    sigma_c = mu_c * max(0.01, cov_c)

    mu_phi = mat.phi_deg
    sigma_phi = mu_phi * max(0.01, cov_phi)

    # 4 个估计点及其权重
    pts = [
        (mu_c + sigma_c, mu_phi + sigma_phi, (1.0 + rho_c_phi) / 4.0),
        (mu_c + sigma_c, mu_phi - sigma_phi, (1.0 - rho_c_phi) / 4.0),
        (mu_c - sigma_c, mu_phi + sigma_phi, (1.0 - rho_c_phi) / 4.0),
        (mu_c - sigma_c, mu_phi - sigma_phi, (1.0 + rho_c_phi) / 4.0),
    ]

    base_slices, info, err_msg = create_slices(
        geom=geom,
        materials=materials,
        xc=xc, yc=yc, R=R,
        n_slices=25,
        rainfall_depth=rainfall_depth,
        kh=kh
    )
    if not base_slices or not info:
        return {"success": False, "error": err_msg or "几何剖分失败"}

    x_edges = info[2]
    e_fs = 0.0
    e_fs2 = 0.0

    for c_val, phi_val, weight in pts:
        c_val = max(0.1, c_val)
        phi_rad = np.radians(np.clip(phi_val, 1.0, 50.0))
        for s in base_slices:
            s.c = c_val
            s.phi = phi_rad

        solver = BishopSolver(base_slices, xc, yc, R, geom, x_edges, tol=1e-3, max_iter=25)
        fs, _ = solver.solve()
        fs_val = fs if fs is not None else 1.0
        e_fs += weight * fs_val
        e_fs2 += weight * (fs_val ** 2)

    var_fs = max(1e-5, e_fs2 - (e_fs ** 2))
    std_fs = np.sqrt(var_fs)
    beta = (e_fs - 1.0) / std_fs
    pf = float(norm.cdf(-beta))

    return {
        "success": True,
        "method": "Rosenblueth 点估计法",
        "fs_mean": float(e_fs),
        "fs_std": float(std_fs),
        "fs_cov": float(std_fs / max(1e-4, e_fs)),
        "beta": float(beta),
        "pf": pf,
        "pf_percent": float(pf * 100.0)
    }