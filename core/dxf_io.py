# -*- coding: utf-8 -*-
"""
AutoCAD DXF 矢量数据交换模块
仅针对边坡地表轮廓线进行导入与导出
采用严格符合 AutoCAD R12 (AC1009) 标准规范的纯文本格式，全面兼容 AutoCAD 2000 至 AutoCAD 2024+ 各版本
"""
from typing import List, Tuple


def export_ground_dxf(filepath: str, ground_pts: List[Tuple[float, float]], layer_name: str = "SLOPE_GROUND") -> bool:
    """
    仅导出地表轮廓线为标准 AutoCAD DXF 文件
    使用标准 R12 POLYLINE/VERTEX 结构，确保 AutoCAD 2022 能够正常打开
    """
    if not ground_pts or len(ground_pts) < 2:
        return False

    try:
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
            "70", "1",
            "0", "LAYER",
            "2", layer_name,
            "70", "0",
            "62", "7",
            "6", "CONTINUOUS",
            "0", "ENDTAB",
            "0", "ENDSEC",
            "0", "SECTION",
            "2", "BLOCKS",
            "0", "ENDSEC",
            "0", "SECTION",
            "2", "ENTITIES",
            "0", "POLYLINE",
            "8", layer_name,
            "66", "1",
            "70", "0",
            "10", "0.0",
            "20", "0.0",
            "30", "0.0"
        ]

        # 逐点写入顶点实体 VERTEX
        for x, y in ground_pts:
            lines.extend([
                "0", "VERTEX",
                "8", layer_name,
                "10", f"{float(x):.4f}",
                "20", f"{float(y):.4f}",
                "30", "0.0"
            ])

        lines.extend([
            "0", "SEQEND",
            "8", layer_name,
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
    """
    从 DXF 文件中解析地表线顶点
    兼容解析 VERTEX (R12/经典多段线)、LWPOLYLINE (AutoCAD 2000~2024 轻量多段线) 以及 LINE 实体
    """
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

        # 1. 经典多段线顶点 VERTEX (AutoCAD R12 及经典 POLYLINE)
        if code == "0" and val == "VERTEX":
            x, y = None, None
            i += 2
            while i < n - 1:
                sub_code = raw_lines[i]
                sub_val = raw_lines[i + 1]
                if sub_code == "0":
                    break
                if sub_code == "10":
                    x = float(sub_val)
                elif sub_code == "20":
                    y = float(sub_val)
                i += 2
            if x is not None and y is not None:
                pts.append((x, y))
            continue

        # 2. 现代轻量多段线 LWPOLYLINE (AutoCAD 2000~2024 默认绘制实体)
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

        # 3. 离散线段 LINE
        elif code == "0" and val == "LINE":
            x1, y1, x2, y2 = None, None, None, None
            i += 2
            while i < n - 1:
                sub_code = raw_lines[i]
                sub_val = raw_lines[i + 1]
                if sub_code == "0":
                    break
                if sub_code == "10":
                    x1 = float(sub_val)
                elif sub_code == "20":
                    y1 = float(sub_val)
                elif sub_code == "11":
                    x2 = float(sub_val)
                elif sub_code == "21":
                    y2 = float(sub_val)
                i += 2
            if x1 is not None and y1 is not None:
                pts.append((x1, y1))
            if x2 is not None and y2 is not None:
                pts.append((x2, y2))
            continue

        i += 2

    if not pts:
        return []

    # 拓扑清洗：按水平 X 坐标升序排列并去除重叠点
    sorted_pts = sorted(pts, key=lambda p: p[0])
    cleaned = [sorted_pts[0]]
    for p in sorted_pts[1:]:
        if abs(p[0] - cleaned[-1][0]) > 1e-4:
            cleaned.append(p)
        elif p[1] > cleaned[-1][1]:
            cleaned[-1] = p

    return cleaned