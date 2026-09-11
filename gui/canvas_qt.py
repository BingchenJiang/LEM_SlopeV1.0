# -*- coding: utf-8 -*-
"""
基于 PyQt5 QGraphicsView 的专业 CAD 级边坡交互视口
支持多层地层线、地下水位线、降雨湿润锋、坡顶荷载与微元物理量悬停交互
"""
import numpy as np
from PyQt5.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPolygonItem,
    QGraphicsPathItem, QGraphicsLineItem
)
from PyQt5.QtGui import QPen, QBrush, QColor, QPainter, QPolygonF, QPainterPath
from PyQt5.QtCore import Qt, QPointF, QRectF, QLineF


class SliceGraphicsItem(QGraphicsPolygonItem):
    """具有悬停高亮与力学物理量 Tooltip 的土条交互图元"""
    def __init__(self, slice_data, polygon: QPolygonF):
        super().__init__(polygon)
        self.slice_data = slice_data
        
        self.default_brush = QBrush(QColor(243, 156, 18, 55))
        self.hover_brush = QBrush(QColor(231, 76, 60, 180))
        self.setBrush(self.default_brush)
        
        pen = QPen(QColor(127, 140, 141), 1)
        pen.setCosmetic(True)
        self.setPen(pen)
        
        self.setAcceptHoverEvents(True)
        self._update_tooltip()

    def _update_tooltip(self):
        s = self.slice_data
        tip = (
            f"<div style='font-family: Microsoft YaHei, SimHei; font-size: 12px; color: #2c3e50;'>"
            f"<b>【土条 #{s.index} 受力与几何参数】</b><hr style='margin: 4px 0;'>"
            f"<b>所属土层:</b> {s.layer_name}<br>"
            f"<b>水平中点 X:</b> {s.xm:.2f} m<br>"
            f"<b>条块宽度 b:</b> {s.b:.2f} m | <b>平均高度 h:</b> {s.h:.2f} m<br>"
            f"<b>土体净自重:</b> {s.W_soil:.2f} kN<br>"
            f"<b>坡顶附加荷载:</b> {s.q_load:.2f} kN<br>"
            f"<b>总竖向力 W:</b> {s.W:.2f} kN<br>"
            f"<b>水平地震惯性力 Fh:</b> {s.Fh:.2f} kN (kh={s.kh:.2f})<br>"
            f"<b>孔隙水压力 u:</b> {s.u:.2f} kPa<br>"
            f"<b>非饱和基质吸力:</b> {s.suction:.2f} kPa<br>"
            f"<b>综合黏聚力 c_total:</b> {s.c:.2f} kPa (含吸力增量)<br>"
            f"<b>有效摩擦角 φ':</b> {np.degrees(s.phi):.2f}°<br>"
            f"<b>底坡倾角 α:</b> {np.degrees(s.alpha):.2f}° | <b>底弧长 l:</b> {s.l:.2f} m"
            f"</div>"
        )
        self.setToolTip(tip)

    def hoverEnterEvent(self, event):
        self.setBrush(self.hover_brush)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setBrush(self.default_brush)
        super().hoverLeaveEvent(event)


class SlopeGraphicsView(QGraphicsView):
    """基于 PyQt5 QGraphicsView 的专业 CAD 级交互视口"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.setRenderHint(QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

        self.scale(1, -1)
        self.setBackgroundBrush(QBrush(QColor(250, 252, 255)))

        self._is_panning = False
        self._pan_start_pos = None

    def fit_view_to_slope(self, margin_ratio: float = 0.15):
        rect = self.scene.sceneRect()
        if rect.isEmpty():
            return
        dx = rect.width() * margin_ratio
        dy = rect.height() * margin_ratio
        target_rect = rect.adjusted(-dx, -dy, dx, dy)
        self.fitInView(target_rect, Qt.KeepAspectRatio)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            factor = 1.15
        elif delta < 0:
            factor = 1.0 / 1.15
        else:
            factor = 1.0
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            self._is_panning = True
            self._pan_start_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_panning:
            delta = event.pos() - self._pan_start_pos
            self._pan_start_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() + delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            self._is_panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self.fit_view_to_slope()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect)
        painter.save()
        grid_pen = QPen(QColor(232, 236, 241), 1, Qt.DotLine)
        grid_pen.setCosmetic(True)
        painter.setPen(grid_pen)

        step = 5.0
        left = int(rect.left() / step) * step
        right = rect.right()
        bottom = int(rect.top() / step) * step
        top = rect.bottom()

        x = left
        while x <= right:
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            x += step

        y = bottom
        while y <= top:
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            y += step

        painter.restore()

    def render_model(
        self,
        ground_x: list,
        ground_y: list,
        xc: float,
        yc: float,
        R: float,
        slices: list = None,
        water_pts: list = None,
        strata_boundaries: list = None,
        rainfall_depth: float = 0.0,
        surcharge_loads: list = None,
        slip_surface = None
    ):
        self.scene.clear()
        if len(ground_x) < 2:
            return

        min_y = min(ground_y) - 6.0
        max_y = max(ground_y) + 8.0
        min_x = ground_x[0] - 5.0
        max_x = ground_x[-1] + 5.0

        # 1. 边坡基底多边形
        poly_pts = [QPointF(ground_x[0], min_y)]
        for x, y in zip(ground_x, ground_y):
            poly_pts.append(QPointF(x, y))
        poly_pts.append(QPointF(ground_x[-1], min_y))

        soil_item = QGraphicsPolygonItem(QPolygonF(poly_pts))
        soil_item.setBrush(QBrush(QColor(245, 247, 250)))
        pen_ground = QPen(QColor(44, 62, 80), 2.0)
        pen_ground.setCosmetic(True)
        soil_item.setPen(pen_ground)
        self.scene.addItem(soil_item)

        # 2. 绘制多层地层分界面
        if strata_boundaries:
            for b_line in strata_boundaries:
                if len(b_line) >= 2:
                    p = QPainterPath()
                    p.moveTo(b_line[0][0], b_line[0][1])
                    for pt in b_line[1:]:
                        p.lineTo(pt[0], pt[1])
                    item_strata = QGraphicsPathItem(p)
                    pen_strata = QPen(QColor(142, 68, 173), 1.5, Qt.DashLine)
                    pen_strata.setCosmetic(True)
                    item_strata.setPen(pen_strata)
                    self.scene.addItem(item_strata)

        # 3. 绘制降雨湿润锋浸润带阴影
        if rainfall_depth > 0.0:
            rain_poly_pts = []
            for x, y in zip(ground_x, ground_y):
                rain_poly_pts.append(QPointF(x, y))
            for x, y in reversed(list(zip(ground_x, ground_y))):
                rain_poly_pts.append(QPointF(x, y - rainfall_depth))
            rain_item = QGraphicsPolygonItem(QPolygonF(rain_poly_pts))
            rain_item.setBrush(QBrush(QColor(52, 152, 219, 45)))
            pen_rain = QPen(QColor(52, 152, 219), 1, Qt.DotLine)
            pen_rain.setCosmetic(True)
            rain_item.setPen(pen_rain)
            self.scene.addItem(rain_item)

        # 4. 绘制地下水浸润线
        if water_pts and len(water_pts) >= 2:
            water_path = QPainterPath()
            water_path.moveTo(water_pts[0][0], water_pts[0][1])
            for pt in water_pts[1:]:
                water_path.lineTo(pt[0], pt[1])
            water_item = QGraphicsPathItem(water_path)
            water_pen = QPen(QColor(41, 128, 185), 1.8, Qt.DashDotLine)
            water_pen.setCosmetic(True)
            water_item.setPen(water_pen)
            self.scene.addItem(water_item)

        # 5. 绘制坡顶附加均布荷载
        if surcharge_loads:
            for x1, x2, q in surcharge_loads:
                if q > 0:
                    y1 = float(np.interp(x1, ground_x, ground_y)) + 0.8
                    y2 = float(np.interp(x2, ground_x, ground_y)) + 0.8
                    load_line = QGraphicsLineItem(x1, y1, x2, y2)
                    pen_load = QPen(QColor(192, 57, 43), 3.0)
                    pen_load.setCosmetic(True)
                    load_line.setPen(pen_load)
                    self.scene.addItem(load_line)

        # 6. 绘制滑面几何轮廓 (智能区分圆弧与折线)
        SLIP_COLOR = QColor(192, 57, 43)

        if slip_surface is not None and getattr(slip_surface, "surface_type", "") == "polygonal":
            # ---------- 非圆弧: 画折线 ----------
            poly_path = QPainterPath()
            poly_path.moveTo(slip_surface.px[0], slip_surface.py[0])
            for px, py in zip(slip_surface.px[1:], slip_surface.py[1:]):
                poly_path.lineTo(px, py)
            poly_item = QGraphicsPathItem(poly_path)
            poly_pen = QPen(SLIP_COLOR, 2.2, Qt.DashLine)
            poly_pen.setCosmetic(True)
            poly_item.setPen(poly_pen)
            self.scene.addItem(poly_item)

        else:
            # ---------- 圆弧: 只画扇形 (两条半径 + 弧段) ----------
            if R is not None and R > 0:
                # 求滑弧与地表的两个交点: (x_start, y_start), (x_end, y_end)
                gx_arr = np.array(ground_x, dtype=float)
                gy_arr = np.array(ground_y, dtype=float)

                # 用解析方法求交点: 圆 y = yc - sqrt(R² - (x-xc)²) 与地表线
                xs_samp = np.linspace(xc - R + 1e-4, xc + R - 1e-4, 1500)
                ys_circ = yc - np.sqrt(np.maximum(0.0, R**2 - (xs_samp - xc)**2))
                ys_grnd = np.interp(xs_samp, gx_arr, gy_arr)
                inside = np.where(ys_circ - ys_grnd < 0)[0]

                if len(inside) >= 2:
                    x_s = float(xs_samp[inside[0]])
                    x_e = float(xs_samp[inside[-1]])
                else:
                    # 退化情况: 用整个可见范围
                    x_s = float(xc - R)
                    x_e = float(xc + R)

                # 采样弧段
                n_arc = 200
                arc_xs = np.linspace(x_s, x_e, n_arc)
                arc_ys = yc - np.sqrt(np.maximum(0.0, R**2 - (arc_xs - xc)**2))

                # --- 弧段 ---
                arc_path = QPainterPath()
                arc_path.moveTo(arc_xs[0], arc_ys[0])
                for ax, ay in zip(arc_xs[1:], arc_ys[1:]):
                    arc_path.lineTo(ax, ay)
                arc_item = QGraphicsPathItem(arc_path)
                arc_pen = QPen(SLIP_COLOR, 2.2, Qt.DashLine)
                arc_pen.setCosmetic(True)
                arc_item.setPen(arc_pen)
                self.scene.addItem(arc_item)

                # --- 两条半径 ---
                r_pen = QPen(SLIP_COLOR, 1.6, Qt.DashLine)
                r_pen.setCosmetic(True)

                line_l = QGraphicsLineItem(
                    QLineF(xc, yc, float(arc_xs[0]), float(arc_ys[0]))
                )
                line_l.setPen(r_pen)
                self.scene.addItem(line_l)

                line_r = QGraphicsLineItem(
                    QLineF(xc, yc, float(arc_xs[-1]), float(arc_ys[-1]))
                )
                line_r.setPen(r_pen)
                self.scene.addItem(line_r)

            # --- 圆心十字 (不变) ---
            cs = max(1.0, (R * 0.03) if R else 1.5)
            c_h = QGraphicsLineItem(xc - cs, yc, xc + cs, yc)
            c_v = QGraphicsLineItem(xc, yc - cs, xc, yc + cs)
            c_pen = QPen(SLIP_COLOR, 2.0)
            c_pen.setCosmetic(True)
            c_h.setPen(c_pen); c_v.setPen(c_pen)
            self.scene.addItem(c_h); self.scene.addItem(c_v)

        # 7. 绘制各个离散切片土条多边形 (直接使用土条底面 y_base，不再用圆方程硬算!)
        if slices:
            for s in slices:
                xl = s.xm - 0.5 * s.b
                xr = s.xm + 0.5 * s.b
                yt_l = float(np.interp(xl, ground_x, ground_y))
                yt_r = float(np.interp(xr, ground_x, ground_y))
                # 真实底高程：直接使用土条自身计算的 y_base
                yb = s.y_base

                slice_poly = QPolygonF([
                    QPointF(xl, yb),
                    QPointF(xr, yb),
                    QPointF(xr, yt_r),
                    QPointF(xl, yt_l)
                ])
                slice_item = SliceGraphicsItem(s, slice_poly)
                self.scene.addItem(slice_item)

                # 计算场景范围时, 把圆弧也纳入
        scene_min_x = min_x
        scene_max_x = max_x
        scene_min_y = min_y
        scene_max_y = max_y

        if slip_surface is None or getattr(slip_surface, "surface_type", "") != "polygonal":
            if R is not None and R > 0:
                scene_min_x = min(scene_min_x, xc - R - 2.0)
                scene_max_x = max(scene_max_x, xc + R + 2.0)
                scene_min_y = min(scene_min_y, yc - R - 2.0)
                scene_max_y = max(scene_max_y, yc + R + 2.0)

        self.scene.setSceneRect(
            scene_min_x, scene_min_y,
            (scene_max_x - scene_min_x) * 1.05,
            (scene_max_y - scene_min_y) * 1.05,
        )