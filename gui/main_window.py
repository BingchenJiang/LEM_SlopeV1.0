# -*- coding: utf-8 -*-
"""
PyQt5 桌面端主窗口：集成菜单栏、控制面板、交互画布、搜索调度与结果面板
"""
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QMessageBox, QStatusBar, QApplication, QPushButton
)
from PyQt5.QtCore import Qt

from core.geometry import SlopeGeometry
from core.slicing import create_slices
from core.solvers import (
    FelleniusSolver, BishopSolver, JanbuSolver,
    SpencerSolver, MorgensternPriceSolver
)
from core.search import (
    PSOSearcher, SimulatedAnnealingSearcher,
    DifferentialEvolutionSearcher, NelderMeadSearcher, GridSearcher
)
from gui.dock_params import ParamsDockWidget
from gui.dock_results import ResultsDockWidget
from gui.canvas_qt import SlopeGraphicsView


class MainWindow(QMainWindow):
    """边坡极限平衡分析系统主窗口"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("边坡极限平衡法稳定性分析平台 (LEM-Slope-Studio) — 经典模型与智能寻优")
        self.resize(1320, 860)

        self.current_slices = None
        self.slice_info = None
        self.current_geom = None
        self.searched_best_params = None
        self._initial_fit_done = False  # 首次呈现标记

        self._init_ui()
        self.on_params_changed()

    def _init_ui(self):
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        h_splitter = QSplitter(Qt.Horizontal)

        # 1. 左侧参数配置面板
        self.dock_params = ParamsDockWidget(self)
        self.dock_params.params_changed.connect(self.on_params_changed)
        self.dock_params.calculate_requested.connect(self.on_calculate_requested)
        self.dock_params.search_requested.connect(self.on_search_requested)
        self.dock_params.apply_searched_circle.connect(self.on_apply_searched_circle)
        h_splitter.addWidget(self.dock_params)

        # 2. 右侧垂直分割：上方绘图视口，下方计算结果表格
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # 视口辅助操作栏（CAD 级快速居中复位按钮）
        view_tools = QHBoxLayout()
        btn_zoom_fit = QPushButton("全屏居中 (Zoom Extents)")
        btn_zoom_fit.setToolTip("按比例自动将边坡居中铺满视口 (双击鼠标中键亦可)")
        btn_zoom_fit.setStyleSheet("padding: 4px 10px; font-weight: bold;")
        btn_zoom_fit.clicked.connect(lambda: self.canvas.fit_view_to_slope(margin_ratio=0.15))
        view_tools.addWidget(btn_zoom_fit)
        view_tools.addStretch()
        right_layout.addLayout(view_tools)

        # 原生 QGraphicsView CAD 级视口
        self.canvas = SlopeGraphicsView(self)
        right_layout.addWidget(self.canvas, stretch=3)

        # 结果与条块明细面板
        self.dock_results = ResultsDockWidget(self)
        right_layout.addWidget(self.dock_results, stretch=2)

        h_splitter.addWidget(right_widget)
        h_splitter.setStretchFactor(0, 1)
        h_splitter.setStretchFactor(1, 3)

        main_layout.addWidget(h_splitter)
        self.setCentralWidget(main_widget)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("系统就绪，已载入标准基准边坡算例与智能寻优算法引擎。")

    def showEvent(self, event):
        """窗口首次呈现在屏幕上时，视口具有了真实像素尺寸，自动触发一次全局自适应居中"""
        super().showEvent(event)
        if not self._initial_fit_done:
            self._initial_fit_done = True
            self.canvas.fit_view_to_slope(margin_ratio=0.15)

    def on_params_changed(self):
        """响应参数修改，重新切片并实时重绘边坡"""
        ground_x, ground_y, ground_pts = self.dock_params.get_geometry_data()
        if len(ground_pts) < 2:
            return

        water_table_pts = [(x, y - 3.0 if y > 3.0 else 0.0) for x, y in ground_pts]
        self.current_geom = SlopeGeometry(ground_pts, water_table_pts)
        
        material = self.dock_params.get_material()
        xc, yc, R, n_slices = self.dock_params.get_circle_params()
        ru, use_water_table = self.dock_params.get_water_condition()

        self.current_slices, self.slice_info, msg = create_slices(
            self.current_geom, material, xc, yc, R,
            n_slices=n_slices, ru=ru, use_water_table=use_water_table
        )

        water_y_plot = [self.current_geom.get_water_elevation(x) for x in ground_x] if use_water_table else None
        self.canvas.render_model(ground_x, ground_y, xc, yc, R, self.current_slices, water_y_plot)
        self.dock_results.display_slices(self.current_slices)
        self.status_bar.showMessage(msg)

    def on_calculate_requested(self):
        """执行所有经典土力学极限平衡求解器"""
        self.on_params_changed()
        if not self.current_slices or not self.slice_info:
            QMessageBox.warning(self, "几何异常", "当前滑弧未能在边坡土体内部形成有效滑动面，请调整圆心或半径！")
            return

        xc, yc, R, _ = self.dock_params.get_circle_params()
        x_edges = self.slice_info[2]

        solvers = [
            ("瑞典条分法 (Fellenius / Ordinary)", FelleniusSolver(self.current_slices, xc, yc, R, self.current_geom, x_edges)),
            ("简化毕肖普法 (Simplified Bishop)", BishopSolver(self.current_slices, xc, yc, R, self.current_geom, x_edges)),
            ("简化让布法 (Simplified Janbu)", JanbuSolver(self.current_slices, xc, yc, R, self.current_geom, x_edges)),
            ("斯宾塞法 (Spencer 完全平衡法)", SpencerSolver(self.current_slices, xc, yc, R, self.current_geom, x_edges)),
            ("摩根斯坦-普赖斯法 (Morgenstern-Price / GLE)", MorgensternPriceSolver(self.current_slices, xc, yc, R, self.current_geom, x_edges, interslice_func="half_sine")),
        ]

        results = []
        for name, solver in solvers:
            fs, note = solver.solve()
            results.append((name, (fs, note)))

        self.dock_results.display_summary(results)
        self.status_bar.showMessage("全部经典极限平衡模型分析完成！")

    def on_search_requested(self):
        """执行临界最危险滑面自动寻优"""
        ground_x, ground_y, ground_pts = self.dock_params.get_geometry_data()
        if len(ground_pts) < 2:
            return
        
        water_table_pts = [(x, y - 3.0 if y > 3.0 else 0.0) for x, y in ground_pts]
        self.current_geom = SlopeGeometry(ground_pts, water_table_pts)
        material = self.dock_params.get_material()
        ru, use_water_table = self.dock_params.get_water_condition()

        algo_name, eval_name, bounds = self.dock_params.get_search_config()
        self.status_bar.showMessage(f"正在采用 [{algo_name}] 智能搜索临界最危险滑面...")
        self.dock_params.prog_bar.setValue(0)

        # 根据算法选择实例化求解器
        if "PSO" in algo_name:
            searcher = PSOSearcher(self.current_geom, material, bounds, eval_method=eval_name, ru=ru, use_water_table=use_water_table, n_particles=25, max_iter=30)
        elif "退火" in algo_name:
            searcher = SimulatedAnnealingSearcher(self.current_geom, material, bounds, eval_method=eval_name, ru=ru, use_water_table=use_water_table)
        elif "差分进化" in algo_name:
            searcher = DifferentialEvolutionSearcher(self.current_geom, material, bounds, eval_method=eval_name, ru=ru, use_water_table=use_water_table, popsize=10, maxiter=20)
        elif "单纯形" in algo_name:
            searcher = NelderMeadSearcher(self.current_geom, material, bounds, eval_method=eval_name, ru=ru, use_water_table=use_water_table)
        else:
            searcher = GridSearcher(self.current_geom, material, bounds, eval_method=eval_name, ru=ru, use_water_table=use_water_table, nx=10, ny=10, nr=8)

        def progress_cb(current, total, current_best):
            pct = int(current / max(1, total) * 100)
            self.dock_params.prog_bar.setValue(min(100, pct))
            self.dock_params.lbl_best_fs.setText(f"{current_best:.4f} (搜索中...)")
            QApplication.processEvents()

        best_fs, best_params, info_msg = searcher.search(progress_callback=progress_cb)
        self.dock_params.prog_bar.setValue(100)
        self.searched_best_params = best_params

        bx, by, br = best_params[0], best_params[1], best_params[2]
        self.dock_params.lbl_best_circle.setText(f"Xc={bx:.2f}m, Yc={by:.2f}m, R={br:.2f}m")
        self.dock_params.lbl_best_fs.setText(f"{best_fs:.4f}")
        self.status_bar.showMessage(f"寻优完成: {info_msg}，最小安全系数 Fs = {best_fs:.4f}")

    def on_apply_searched_circle(self):
        """将寻优得到的临界滑弧应用至主模型并触发 5 种 LEM 求解"""
        if self.searched_best_params is None:
            QMessageBox.information(self, "提示", "请先点击启动搜索获得最危险滑面！")
            return

        bx, by, br = self.searched_best_params[0], self.searched_best_params[1], self.searched_best_params[2]
        self.dock_params.set_circle_params(bx, by, br)
        self.on_params_changed()
        self.on_calculate_requested()
        QMessageBox.information(self, "应用成功", f"已成功载入最危险滑面：\nXc={bx:.2f} m, Yc={by:.2f} m, R={br:.2f} m\n已自动完成 5 种经典 LEM 模型复核！")