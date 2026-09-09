# -*- coding: utf-8 -*-
"""
AutoCAD DXF 矢量数据交换模块
支持边坡地表线、任意起伏多层地层分界线与地下水位线的分图层导出
采用严格符合 AutoCAD R12 (AC1009) 标准规范的纯文本格式，全面兼容 AutoCAD 2000 至 AutoCAD 2024+ 各版本
"""
from typing import List, Tuple, Optional


def export_model_dxf(
    filepath: str,
    ground_pts: List[Tuple[float, float]],
    strata_lines: Optional[List[List[Tuple[float, float]]]] = None,
    water_pts: Optional[List[Tuple[float, float]]] = None
) -> bool:
    """
    分图层导出边坡几何模型至 CAD DXF 文件：
    - 0_GROUND_SURFACE: 地表轮廓线 (颜色: 7-白色)
    - 1_STRATA_LAYER_k: 各地层分界面 (分配不同颜色: 青/洋红/黄/绿)
    - 2_PHREATIC_WATER: 地下水浸润线 (颜色: 5-蓝色)
    """
    if not ground_pts or len(ground_pts) < 2:
        return False

    try:
        layer_defs = [("0_GROUND_SURFACE", 7, "CONTINUOUS")]
        if strata_lines:
            palette = [4, 6, 2, 3, 1]  # 青色, 洋红色, 黄色, 绿色, 红色
            for idx in range(len(strata_lines)):
                color = palette[idx % len(palette)]
                layer_defs.append((f"1_STRATA_LAYER_{idx + 1}", color, "CONTINUOUS"))
        if water_pts and len(water_pts) >= 2:
            layer_defs.append(("2_PHREATIC_WATER", 5, "CONTINUOUS"))

        lines = [
            "0", "SECTION",
            "2", "HEADER",
            "9", "$ACADVER",
            "1", "AC1009",
            "0", "ENDSEC",
            "0", "SECTION",
            "2", "TABLES",
            "0", "TABLE",
            "2", "LAYER",
            "70", str(len(layer_defs))
        ]

        for lname, lcolor, ltype in layer_defs:
            lines.extend([
                "0", "LAYER",
                "2", lname,
                "70", "0",
                "62", str(lcolor),
                "6", ltype
            ])

        lines.extend([
            "0", "ENDTAB",
            "0", "ENDSEC",
            "0", "SECTION",
            "2", "BLOCKS",
            "0", "ENDSEC",
            "0", "SECTION",
            "2", "ENTITIES"
        ])

        def write_polyline(pts, layer_name):
            p_lines = [
                "0", "POLYLINE",
                "8", layer_name,
                "66", "1",
                "70", "0",
                "10", "0.0",
                "20", "0.0",
                "30", "0.0"
            ]
            for x, y in pts:
                p_lines.extend([
                    "0", "VERTEX",
                    "8", layer_name,
                    "10", f"{float(x):.4f}",
                    "20", f"{float(y):.4f}",
                    "30", "0.0"
                ])
            p_lines.extend([
                "0", "SEQEND",
                "8", layer_name
            ])
            return p_lines

        lines.extend(write_polyline(ground_pts, "0_GROUND_SURFACE"))

        if strata_lines:
            for idx, s_line in enumerate(strata_lines):
                if len(s_line) >= 2:
                    lines.extend(write_polyline(s_line, f"1_STRATA_LAYER_{idx + 1}"))

        if water_pts and len(water_pts) >= 2:
            lines.extend(write_polyline(water_pts, "2_PHREATIC_WATER"))

        lines.extend([
            "0", "ENDSEC",
            "0", "EOF"
        ])

        content = "\n".join(lines) + "\n"
        with open(filepath, "w", encoding="ascii") as f:
            f.write(content)
        return True
    except Exception:
        return False


def import_dxf_polyline(filepath: str) -> List[Tuple[float, float]]:
    """从 DXF 文件中解析地表线顶点"""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            raw_lines = [line.strip() for line in f]
    except Exception:
        return []

    pts = []
    i = 0
    n = len(raw_lines)

    while i < n - 1:
        code = raw_lines[i]
        val = raw_lines[i + 1]

        if code == "0" and val == "VERTEX":
            x, y = None, None
            i += 2
            while i < n - 1:
                sub_code = raw_lines[i]
                sub_val = raw_lines[i + 1]
                if sub_code == "0":
                    break
                if sub_code == "10": x = float(sub_val)
                elif sub_code == "20": y = float(sub_val)
                i += 2
            if x is not None and y is not None:
                pts.append((x, y))
            continue

        elif code == "0" and val == "LWPOLYLINE":
            i += 2
            cur_x = None
            while i < n - 1:
                sub_code = raw_lines[i]
                sub_val = raw_lines[i + 1]
                if sub_code == "0":
                    break
                if sub_code == "10":
                    cur_x = float(sub_val)
                elif sub_code == "20" and cur_x is not None:
                    pts.append((cur_x, float(sub_val)))
                    cur_x = None
                i += 2
            continue

        elif code == "0" and val == "LINE":
            x1, y1, x2, y2 = None, None, None, None
            i += 2
            while i < n - 1:
                sub_code = raw_lines[i]
                sub_val = raw_lines[i + 1]
                if sub_code == "0":
                    break
                if sub_code == "10": x1 = float(sub_val)
                elif sub_code == "20": y1 = float(sub_val)
                elif sub_code == "11": x2 = float(sub_val)
                elif sub_code == "21": y2 = float(sub_val)
                i += 2
            if x1 is not None and y1 is not None:
                pts.append((x1, y1))
            if x2 is not None and y2 is not None:
                pts.append((x2, y2))
            continue

        i += 2

    if not pts:
        return []

    sorted_pts = sorted(pts, key=lambda p: p[0])
    cleaned = [sorted_pts[0]]
    for p in sorted_pts[1:]:
        if abs(p[0] - cleaned[-1][0]) > 1e-4:
            cleaned.append(p)
        elif p[1] > cleaned[-1][1]:
            cleaned[-1] = p

    return cleaned