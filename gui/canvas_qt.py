# -*- coding: utf-8 -*-
"""
基于 Qt Graphics View Framework (QGraphicsView / QGraphicsScene) 的专业 CAD 级交互画布
"""
import numpy as np

try:
    from PyQt5.QtWidgets import (
        QGraphicsView, QGraphicsScene, QGraphicsPolygonItem,
        QGraphicsPathItem, QGraphicsLineItem
    )
    from PyQt5.QtGui import QPen, QBrush, QColor, QPainter, QPolygonF, QPainterPath
    from PyQt5.QtCore import Qt, QPointF, QRectF
except ImportError:
    from PyQt6.QtWidgets import (
        QGraphicsView, QGraphicsScene, QGraphicsPolygonItem,
        QGraphicsPathItem, QGraphicsLineItem
    )
    from PyQt6.QtGui import QPen, QBrush, QColor, QPainter, QPolygonF, QPainterPath
    from PyQt6.QtCore import Qt, QPointF, QRectF


class SliceGraphicsItem(QGraphicsPolygonItem):
    """具有悬停高亮与力学物理量 Tooltip 的土条交互图元"""
    def __init__(self, slice_data, polygon: QPolygonF):
        super().__init__(polygon)
        self.slice_data = slice_data
        
        # 默认半透明填充与悬停高亮填充
        self.default_brush = QBrush(QColor(243, 156, 18, 50))
        self.hover_brush = QBrush(QColor(231, 76, 60, 170))
        self.setBrush(self.default_brush)
        
        # 使用 Cosmetic Pen，保证在任意视口缩放级别下线宽均保持为 1px，避免矢量线条随缩放变粗
        pen = QPen(QColor(127, 140, 141), 1)
        pen.setCosmetic(True)
        self.setPen(pen)
        
        self.setAcceptHoverEvents(True)
        self._update_tooltip()

    def _update_tooltip(self):
        s = self.slice_data
        tip = (
            f"<div style='font-family: Microsoft YaHei, SimHei; font-size: 12px; color: #2c3e50;'>"
            f"<b>【土条 #{s.index} 微元物理力学参数】</b><hr style='margin: 4px 0;'>"
            f"<b>水平中点 X:</b> {s.xm:.2f} m<br>"
            f"<b>条块宽度 b:</b> {s.b:.2f} m<br>"
            f"<b>平均高度 h:</b> {s.h:.2f} m<br>"
            f"<b>条块自重 W:</b> {s.W:.2f} kN<br>"
            f"<b>底坡倾角 α:</b> {np.degrees(s.alpha):.2f}°<br>"
            f"<b>底滑面长 l:</b> {s.l:.2f} m<br>"
            f"<b>孔隙水压 u:</b> {s.u:.2f} kPa<br>"
            f"<b>有效黏聚力 c':</b> {s.c:.1f} kPa<br>"
            f"<b>内摩擦角 φ':</b> {np.degrees(s.phi):.1f}°"
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
    """基于 QGraphicsView 的专业 CAD 级边坡交互视口"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        # 开启视口全屏抗锯齿渲染
        render_hint = QPainter.RenderHint.Antialiasing if hasattr(QPainter, 'RenderHint') else QPainter.Antialiasing
        self.setRenderHint(render_hint)

        # 缩放锚点设为当前鼠标光标所在物理位置
        anchor_mouse = QGraphicsView.ViewportAnchor.AnchorUnderMouse if hasattr(QGraphicsView, 'ViewportAnchor') else QGraphicsView.AnchorUnderMouse
        self.setTransformationAnchor(anchor_mouse)
        self.setResizeAnchor(anchor_mouse)

        # 视口变换：垂直翻转 Y 轴，映射为工程高程右手坐标系 (+Y 朝上)
        self.scale(1, -1)
        self.setBackgroundBrush(QBrush(QColor(250, 252, 255)))

        # 拖拽平移状态控制
        self._is_panning = False
        self._pan_start_pos = None

    def wheelEvent(self, event):
        """鼠标滚轮平滑无极缩放 (以光标为中心)"""
        delta = event.angleDelta().y()
        if delta > 0:
            factor = 1.15
        elif delta < 0:
            factor = 1.0 / 1.15
        else:
            factor = 1.0
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        """鼠标中键或右键按住触发自由平移"""
        btn_mid = Qt.MouseButton.MiddleButton if hasattr(Qt, 'MouseButton') else Qt.MiddleButton
        btn_right = Qt.MouseButton.RightButton if hasattr(Qt, 'MouseButton') else Qt.RightButton
        if event.button() in (btn_mid, btn_right):
            self._is_panning = True
            self._pan_start_pos = event.pos()
            cursor_hand = Qt.CursorShape.ClosedHandCursor if hasattr(Qt, 'CursorShape') else Qt.ClosedHandCursor
            self.setCursor(cursor_hand)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_panning:
            delta = event.pos() - self._pan_start_pos
            self._pan_start_pos = event.pos()
            # 根据翻转后的物理坐标更新视口滚动条
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() + delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        btn_mid = Qt.MouseButton.MiddleButton if hasattr(Qt, 'MouseButton') else Qt.MiddleButton
        btn_right = Qt.MouseButton.RightButton if hasattr(Qt, 'MouseButton') else Qt.RightButton
        if event.button() in (btn_mid, btn_right):
            self._is_panning = False
            cursor_arrow = Qt.CursorShape.ArrowCursor if hasattr(Qt, 'CursorShape') else Qt.ArrowCursor
            self.setCursor(cursor_arrow)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def drawBackground(self, painter: QPainter, rect: QRectF):
        """动态绘制 CAD 级工程参考网格"""
        super().drawBackground(painter, rect)
        painter.save()
        grid_pen = QPen(QColor(232, 236, 241), 1, Qt.PenStyle.DotLine if hasattr(Qt, 'PenStyle') else Qt.DotLine)
        grid_pen.setCosmetic(True)
        painter.setPen(grid_pen)

        step = 5.0  # 5 米网格线
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

    def render_model(self, ground_x, ground_y, xc, yc, R, slices=None, water_table_y=None):
        """以原生 QGraphicsItem 构建矢量场景"""
        self.scene.clear()

        if len(ground_x) < 2:
            return

        min_y = min(ground_y) - 6.0
        max_y = max(ground_y) + 8.0
        min_x = ground_x[0] - 5.0
        max_x = ground_x[-1] + 5.0

        # 1. 绘制边坡土体多边形 (QGraphicsPolygonItem)
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

        # 2. 绘制地下水浸润线 (QGraphicsPathItem)
        if water_table_y is not None:
            water_path = QPainterPath()
            water_path.moveTo(ground_x[0], water_table_y[0])
            for x, y in zip(ground_x[1:], water_table_y[1:]):
                water_path.lineTo(x, y)
            water_item = QGraphicsPathItem(water_path)
            water_pen = QPen(QColor(41, 128, 185), 1.8, Qt.PenStyle.DashDotLine if hasattr(Qt, 'PenStyle') else Qt.DashDotLine)
            water_pen.setCosmetic(True)
            water_item.setPen(water_pen)
            self.scene.addItem(water_item)

        # 3. 绘制滑弧整圆参考虚线与圆心十字标 (QGraphicsPathItem / QGraphicsLineItem)
        circle_path = QPainterPath()
        circle_path.addEllipse(QPointF(xc, yc), R, R)
        ref_circle = QGraphicsPathItem(circle_path)
        ref_pen = QPen(QColor(189, 195, 199), 1.0, Qt.PenStyle.DotLine if hasattr(Qt, 'PenStyle') else Qt.DotLine)
        ref_pen.setCosmetic(True)
        ref_circle.setPen(ref_pen)
        self.scene.addItem(ref_circle)

        # 圆心十字光标
        cross_size = 1.0
        c_h = QGraphicsLineItem(xc - cross_size, yc, xc + cross_size, yc)
        c_v = QGraphicsLineItem(xc, yc - cross_size, xc, yc + cross_size)
        c_pen = QPen(QColor(192, 57, 43), 2.0)
        c_pen.setCosmetic(True)
        c_h.setPen(c_pen)
        c_v.setPen(c_pen)
        self.scene.addItem(c_h)
        self.scene.addItem(c_v)

        # 4. 绘制离散土条微元多边形
        if slices:
            for s in slices:
                xl = s.xm - 0.5 * s.b
                xr = s.xm + 0.5 * s.b
                yt_l = float(np.interp(xl, ground_x, ground_y))
                yt_r = float(np.interp(xr, ground_x, ground_y))
                yb_l = float(yc - np.sqrt(max(0, R**2 - (xl - xc)**2)))
                yb_r = float(yc - np.sqrt(max(0, R**2 - (xr - xc)**2)))

                slice_poly = QPolygonF([
                    QPointF(xl, yb_l),
                    QPointF(xr, yb_r),
                    QPointF(xr, yt_r),
                    QPointF(xl, yt_l)
                ])
                slice_item = SliceGraphicsItem(s, slice_poly)
                self.scene.addItem(slice_item)

            # 强调主要临界剪切滑弧线
            slip_path = QPainterPath()
            xs_edge = [s.xm - 0.5 * s.b for s in slices] + [slices[-1].xm + 0.5 * slices[-1].b]
            ys_edge = [float(yc - np.sqrt(max(0, R**2 - (x - xc)**2))) for x in xs_edge]
            slip_path.moveTo(xs_edge[0], ys_edge[0])
            for x, y in zip(xs_edge[1:], ys_edge[1:]):
                slip_path.lineTo(x, y)
            
            slip_item = QGraphicsPathItem(slip_path)
            slip_pen = QPen(QColor(231, 76, 60), 2.5)
            slip_pen.setCosmetic(True)
            slip_item.setPen(slip_pen)
            self.scene.addItem(slip_item)

        # 场景包络范围设定
        self.scene.setSceneRect(min_x, min_y, (max_x - min_x) * 1.05, (max_y - min_y) * 1.05)
        
    def fit_view_to_slope(self, margin_ratio: float = 0.15):
        """让当前边坡全貌按比例饱满填充视口，四周保留留白"""
        rect = self.scene.sceneRect()
        if rect.isEmpty():
            return
        
        # 增加适当四周留白 margin
        dx = rect.width() * margin_ratio
        dy = rect.height() * margin_ratio
        target_rect = rect.adjusted(-dx, -dy, dx, dy)
        
        keep_ratio = Qt.AspectRatioMode.KeepAspectRatio if hasattr(Qt, 'AspectRatioMode') else Qt.KeepAspectRatio
        self.fitInView(target_rect, keep_ratio)

    def mouseDoubleClickEvent(self, event):
        """双击鼠标中键：CAD 经典操作，快速全屏居中复位"""
        btn_mid = Qt.MouseButton.MiddleButton if hasattr(Qt, 'MouseButton') else Qt.MiddleButton
        if event.button() == btn_mid:
            self.fit_view_to_slope()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)