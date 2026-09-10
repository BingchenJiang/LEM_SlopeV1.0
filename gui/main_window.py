# -*- coding: utf-8 -*-
"""
PyQt5 桌面端主窗口：集成标准菜单栏、CAD 矢量视口工具栏、可拆卸 QDockWidget 体系与工程图标
"""
from datetime import datetime
import os
import csv
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QMessageBox, QStatusBar,
    QFileDialog, QAction, QToolBar
)
from PyQt5.QtCore import Qt
from core.reliability.monte_carlo import MonteCarloSimulator
from core.report_generator import generate_report
import numpy as np

from core.geometry import SlopeGeometry
from core.slicing import create_slices
from core.solvers import (
    FelleniusSolver, BishopSolver, JanbuSolver,
    SpencerSolver, MorgensternPriceSolver
)
from core.dxf_io import export_model_dxf, import_dxf_polyline
from core.project_io import save_project_file, load_project_file
from core.threads import OptimizationWorker, ReliabilityWorker
from gui.canvas_qt import SlopeGraphicsView
from gui.icons import get_icon
from gui.dock_widgets import (
    GeometryDockWidget, MaterialDockWidget,
    RainfallDockWidget, LoadsDockWidget,
    SearchDockWidget, ResultsDockWidget, ReliabilityDockWidget
)
from core.reliability.monte_carlo import MonteCarloSimulator
from core.reliability.pem import run_point_estimate_analysis



class MainWindow(QMainWindow):
    """边坡极限平衡分析系统主窗口 (QDockWidget 模块化架构)"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("边坡极限平衡法稳定性分析平台 (LEM-Slope-Studio)")
        self.resize(1440, 920)

        self.current_slices = None
        self.slice_info = None
        self.current_geom = None
        self.searched_best_params = None
        self.current_project_file = None
        self._initial_fit_done = False
        self._search_worker = None
        self._last_search_diagnostics = None

        self._init_central_view()
        self._init_dock_widgets()
        self._init_menu_and_toolbars()
        self.on_params_changed()

    def _init_central_view(self):
        self.canvas = SlopeGraphicsView(self)
        self.setCentralWidget(self.canvas)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("系统就绪，已载入标准多层边坡算例与智能寻优算法引擎。")

    def _init_dock_widgets(self):
        # ============================================================
        # 左侧：几何 / 材料 / 荷载  —— 全部为"建模输入"
        # ============================================================
        self.dock_geom = GeometryDockWidget(self)
        self.dock_geom.geometry_changed.connect(self.on_params_changed)

        self.dock_mat = MaterialDockWidget(self)
        self.dock_mat.materials_changed.connect(self.on_params_changed)

        self.dock_loads = LoadsDockWidget(self)
        self.dock_loads.loads_changed.connect(self.on_params_changed)

        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_geom)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_mat)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_loads)

        # 三个左侧面板合成 Tab
        self.tabifyDockWidget(self.dock_geom, self.dock_mat)
        self.tabifyDockWidget(self.dock_mat, self.dock_loads)
        self.dock_geom.raise_()          # 默认显示第一个

        # ============================================================
        # 右侧：滑面寻优 / 可靠度  —— 全部为"分析控制"
        # ============================================================
        self.dock_search = SearchDockWidget(self)
        self.dock_search.preview_circle_changed.connect(self.on_params_changed)
        self.dock_search.calculate_requested.connect(self.on_calculate_requested)
        self.dock_search.search_requested.connect(self.on_search_requested)
        self.dock_search.search_stop_requested.connect(self.on_search_stop_requested)
        self.dock_search.apply_searched_circle.connect(self.on_apply_searched_circle)

        self.dock_rel = ReliabilityDockWidget(self)
        self.dock_rel.reliability_requested.connect(self.on_reliability_requested)
        self.dock_rel.reliability_stop_requested.connect(self.on_reliability_stop_requested)

        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_search)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_rel)
        self.tabifyDockWidget(self.dock_search, self.dock_rel)
        self.dock_search.raise_()

        # ============================================================
        # 底部：降雨 / 成果  —— 全部为"时程与结果查看"
        # ============================================================
        self.dock_rain = RainfallDockWidget(self)
        self.dock_rain.time_step_changed.connect(self.on_time_step_changed)
        self.dock_rain.solve_time_series_requested.connect(self.on_solve_time_series)

        self.dock_results = ResultsDockWidget(self)
        # 如果有结果相关信号也可以接

        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_rain)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_results)
        self.tabifyDockWidget(self.dock_rain, self.dock_results)
        self.dock_rain.raise_()

        # ============================================================
        # 面板尺寸与角落策略
        # ============================================================
        # 左侧三个面板统一宽度，右侧两个统一宽度
        self.resizeDocks(
            [self.dock_geom, self.dock_mat, self.dock_loads,
            self.dock_search, self.dock_rel],
            [340, 340, 340, 360, 360],
            Qt.Horizontal
        )
        self.resizeDocks([self.dock_rain, self.dock_results], [180, 180], Qt.Vertical)

        # 左右两侧的面板不允许被拖到上下角落
        self.setCorner(Qt.TopLeftCorner,     Qt.LeftDockWidgetArea)
        self.setCorner(Qt.BottomLeftCorner,  Qt.LeftDockWidgetArea)
        self.setCorner(Qt.TopRightCorner,    Qt.RightDockWidgetArea)
        self.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)

        # 限制停靠行为，防止用户拖乱
        self.setDockNestingEnabled(False)
        self.setDockOptions(
            QMainWindow.AnimatedDocks
            | QMainWindow.AllowTabbedDocks
        )

        # 给视口留白：左右各 340px，底部 180px，视口至少 600px 宽
        self.setMinimumSize(1280, 720)        

    def _init_menu_and_toolbars(self):
        menu_bar = self.menuBar()

        # 文件菜单
        file_menu = menu_bar.addMenu("文件(&F)")

        act_new = QAction(get_icon("file_new"), "新建工程(&N)", self)
        act_new.setShortcut("Ctrl+N")
        act_new.triggered.connect(self.on_menu_new)
        file_menu.addAction(act_new)

        act_open = QAction(get_icon("file_open"), "打开工程(&O)...", self)
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self.on_menu_open)
        file_menu.addAction(act_open)

        act_save = QAction(get_icon("file_save"), "保存工程(&S)", self)
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self.on_menu_save)
        file_menu.addAction(act_save)

        act_save_as = QAction(get_icon("file_save"), "工程另存为(&A)...", self)
        act_save_as.setShortcut("Ctrl+Shift+S")
        act_save_as.triggered.connect(self.on_menu_save_as)
        file_menu.addAction(act_save_as)

        file_menu.addSeparator()

        act_import_dxf = QAction(get_icon("import_dxf"), "导入 CAD 地表线 (DXF)...", self)
        act_import_dxf.triggered.connect(self.on_menu_import_dxf)
        file_menu.addAction(act_import_dxf)

        act_export_dxf = QAction(get_icon("export_dxf"), "分图层导出模型至 CAD (DXF)...", self)
        act_export_dxf.triggered.connect(self.on_menu_export_dxf)
        file_menu.addAction(act_export_dxf)

        act_export_csv = QAction(get_icon("export_csv"), "导出切片数据报表 (CSV)...", self)
        act_export_csv.triggered.connect(self.on_menu_export_csv)
        file_menu.addAction(act_export_csv)
        
        act_export_report = QAction(get_icon("export_csv"), "导出计算书 (Markdown)...", self)
        act_export_report.triggered.connect(self.on_menu_export_report)
        file_menu.addAction(act_export_report)

        file_menu.addSeparator()

        act_exit = QAction("退出(&X)", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # 视图与窗口菜单
        view_menu = menu_bar.addMenu("视图与窗口(&V)")

        act_zoom_fit = QAction(get_icon("zoom_extents"), "全屏居中复位 (Zoom Extents)", self)
        act_zoom_fit.setShortcut("F5")
        act_zoom_fit.triggered.connect(lambda: self.canvas.fit_view_to_slope(margin_ratio=0.15))
        view_menu.addAction(act_zoom_fit)

        view_menu.addSeparator()
        view_menu.addAction(self.dock_geom.toggleViewAction())
        view_menu.addAction(self.dock_mat.toggleViewAction())
        view_menu.addAction(self.dock_rain.toggleViewAction())
        view_menu.addAction(self.dock_loads.toggleViewAction())
        view_menu.addAction(self.dock_search.toggleViewAction())
        view_menu.addAction(self.dock_results.toggleViewAction())

        # 分析计算菜单
        calc_menu = menu_bar.addMenu("分析计算(&A)")

        act_run_all = QAction(get_icon("run_solvers"), "运行全部 5 种经典模型求解", self)
        act_run_all.setShortcut("F6")
        act_run_all.triggered.connect(self.on_calculate_requested)
        calc_menu.addAction(act_run_all)

        act_start_search = QAction(get_icon("search_surface"), "启动最危险滑面搜索", self)
        act_start_search.triggered.connect(self.on_search_requested)
        calc_menu.addAction(act_start_search)

        act_time_series = QAction(get_icon("rainfall_time"), "计算降雨全历时稳定性衰减曲线 Fs(t)", self)
        act_time_series.triggered.connect(self.on_solve_time_series)
        calc_menu.addAction(act_time_series)

        # 帮助菜单
        help_menu = menu_bar.addMenu("帮助(&H)")

        act_theory = QAction("极限平衡与非饱和理论说明...", self)
        act_theory.triggered.connect(self.on_menu_theory_help)
        help_menu.addAction(act_theory)

        act_about = QAction("关于 LEM-Slope-Studio...", self)
        act_about.triggered.connect(self.on_menu_about)
        help_menu.addAction(act_about)

        # CAD 视口工具栏
        cad_toolbar = QToolBar("CAD 视口工具栏", self)
        cad_toolbar.addAction(act_zoom_fit)
        cad_toolbar.addSeparator()
        cad_toolbar.addAction(act_run_all)
        cad_toolbar.addAction(act_start_search)
        cad_toolbar.addAction(act_time_series)
        cad_toolbar.addSeparator()
        cad_toolbar.addAction(act_import_dxf)
        cad_toolbar.addAction(act_export_dxf)
        self.addToolBar(Qt.TopToolBarArea, cad_toolbar)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._initial_fit_done:
            self._initial_fit_done = True
            self.canvas.fit_view_to_slope(margin_ratio=0.15)

    def on_params_changed(self):
        """统一读取全部 DockWidget 数据并重新切片渲染"""
        ground_pts = self.dock_geom.get_ground_points()
        if len(ground_pts) < 2:
            return

        water_pts = self.dock_geom.get_water_points()
        strata_lines = self.dock_geom.get_strata_lines()
        materials = self.dock_mat.get_materials_list()
        surcharge = self.dock_loads.get_surcharge_loads()
        kh = self.dock_loads.get_seismic_kh()
        rain_depth = self.dock_rain.get_current_wetting_front_depth()

        # 核心改动：获取真实的滑面对象 (圆弧或折线)
        slip_surface = self.dock_search.get_slip_surface()
        xc, yc, R, n_slices = self.dock_search.get_circle_params()

        self.current_geom = SlopeGeometry(
            ground_coords=ground_pts,
            water_coords=water_pts,
            strata_boundaries=strata_lines,
            surcharge_loads=surcharge
        )

        # 切片器直接传入 slip_surface
        self.current_slices, self.slice_info, msg = create_slices(
            geom=self.current_geom,
            materials=materials,
            slip_surface=slip_surface,
            n_slices=n_slices,
            rainfall_depth=rain_depth,
            kh=kh
        )

        ground_x = [p[0] for p in ground_pts]
        ground_y = [p[1] for p in ground_pts]

        # 画布传入 slip_surface 进行非圆弧渲染
        self.canvas.render_model(
            ground_x=ground_x,
            ground_y=ground_y,
            xc=xc, yc=yc, R=R,
            slices=self.current_slices,
            water_pts=water_pts,
            strata_boundaries=strata_lines,
            rainfall_depth=rain_depth,
            surcharge_loads=surcharge,
            slip_surface=slip_surface
        )
        self.dock_results.display_slices(self.current_slices)
        self.status_bar.showMessage(msg)

    def on_time_step_changed(self, t: float):
        self.on_params_changed()
        self.status_bar.showMessage(f"已切换至降雨历时 t = {t:.1f} h，湿润锋深度已动态更新。")

    def on_solve_time_series(self):
        ground_pts = self.dock_geom.get_ground_points()
        water_pts = self.dock_geom.get_water_points()
        strata_lines = self.dock_geom.get_strata_lines()
        materials = self.dock_mat.get_materials_list()
        surcharge = self.dock_loads.get_surcharge_loads()
        kh = self.dock_loads.get_seismic_kh()
        xc, yc, R, n_slices = self.dock_search.get_circle_params()

        geom = SlopeGeometry(ground_pts, water_pts, strata_lines, surcharge)
        rain_model = self.dock_rain.get_rainfall_model()
        max_t = rain_model.get_max_time()

        if max_t <= 0.0:
            QMessageBox.warning(self, "提示", "降雨时序总历时为0，请在降雨面板中配置时间过程。")
            return

        time_steps = np.linspace(0.0, max_t, 13)
        time_results = []

        for t in time_steps:
            depth = rain_model.get_wetting_front_depth(t)
            intensity = rain_model.get_intensity_at(t)
            slices, info, _ = create_slices(
                geom=geom,
                materials=materials,
                xc=xc,
                yc=yc,
                R=R,
                n_slices=n_slices,
                rainfall_depth=depth,
                kh=kh
            )
            if slices and info:
                b_solver = BishopSolver(slices, xc, yc, R, geom, info[2])
                fs, _ = b_solver.solve()
                fs_val = fs if fs is not None else 0.0
            else:
                fs_val = 0.0
            time_results.append((t, intensity, depth, fs_val))

        self.dock_results.display_time_series(time_results)
        self.status_bar.showMessage(f"降雨全历时 (0 ~ {max_t:.1f} h) 稳定性时程分析完成，已生成衰减表。")

    def on_calculate_requested(self):
        """仅对用户当前选定的滑面，计算用户选定的力学模型"""
        self.on_params_changed()
        if not self.current_slices or not self.slice_info:
            QMessageBox.warning(self, "几何异常",
                                "当前滑面未能在土体内部切出有效滑体，请调整几何输入。")
            return

        method_text = self.dock_search.get_selected_method_name()
        x_edges = self.slice_info[2]
        slip_surface = self.dock_search.get_slip_surface()

        # ============================================================
        # 【P1-2 修复】从 slip_surface 派生 xc / yc / R
        # ------------------------------------------------------------
        # 圆弧模式: 直接从滑面对象取圆心与半径
        # 非圆弧模式: 用折线几何中心做力矩参考点, 用土条底到中心的
        #             最大距离做等效半径 R (只要非零, 力矩方程就能成立)
        # ============================================================
        if slip_surface.surface_type == "circular":
            xc_ = slip_surface.xc
            yc_ = slip_surface.yc
            R_ = slip_surface.R
        else:
            xc_, yc_ = slip_surface.get_moment_center()
            R_ = max(
                float(np.hypot(s.xm - xc_, s.y_base - yc_))
                for s in self.current_slices
            )
            R_ = max(1.0, R_)  # 保证非零

        # 实例化所选求解器（统一传 xc_, yc_, R_）
        solver = None
        if "Spencer" in method_text:
            solver = SpencerSolver(
                self.current_slices, xc_, yc_, R_,
                self.current_geom, x_edges,
                slip_surface=slip_surface
            )
        elif "Morgenstern" in method_text:
            solver = MorgensternPriceSolver(
                self.current_slices, xc_, yc_, R_,
                self.current_geom, x_edges,
                slip_surface=slip_surface
            )
        elif "Janbu" in method_text:
            solver = JanbuSolver(
                self.current_slices, xc_, yc_, R_,
                self.current_geom, x_edges,
                slip_surface=slip_surface
            )
        elif "Bishop" in method_text:
            solver = BishopSolver(
                self.current_slices, xc_, yc_, R_,
                self.current_geom, x_edges,
                slip_surface=slip_surface
            )
        elif "Fellenius" in method_text:
            solver = FelleniusSolver(
                self.current_slices, xc_, yc_, R_,
                self.current_geom, x_edges,
                slip_surface=slip_surface
            )

        if solver is None:
            return

        # 单模型定向求解
        fs, note = solver.solve()
        self.dock_results.display_summary([(method_text.split()[0], (fs, note))])

        if fs is not None:
            self.status_bar.showMessage(
                f"计算完成: {method_text.split()[0]} Fs = {fs:.4f} ({note})"
            )
        else:
            self.status_bar.showMessage(f"计算未收敛: {note}")

    def on_search_requested(self):
        """启动滑面全局寻优 (支持圆弧与非圆弧, 非圆弧支持自动/手动两种模式)"""
        ground_pts = self.dock_geom.get_ground_points()
        water_pts = self.dock_geom.get_water_points()
        strata_lines = self.dock_geom.get_strata_lines()
        materials = self.dock_mat.get_materials_list()
        surcharge = self.dock_loads.get_surcharge_loads()
        kh = self.dock_loads.get_seismic_kh()
        rain_depth = self.dock_rain.get_current_wetting_front_depth()

        self.current_geom = SlopeGeometry(ground_pts, water_pts, strata_lines, surcharge)

        # 6 元组解包
        stype, algo_name, eval_name, bounds, ref_pts, auto_search = \
            self.dock_search.get_search_config()

        mode_str = "自动搜索" if auto_search else "手动试算"
        self.status_bar.showMessage(
            f"正在启动 [{stype} | {mode_str}] 最危险滑面智能搜索..."
        )
        self.dock_search.btn_search.setEnabled(False)
        self.dock_search.btn_stop.setEnabled(True)
        self.dock_search.prog_bar.setValue(0)

        self._search_worker = OptimizationWorker(
            surface_type=stype,
            algo_name=algo_name,
            eval_name=eval_name,
            geom=self.current_geom,
            materials=materials,
            bounds=bounds,
            rainfall_depth=rain_depth,
            kh=kh,
            poly_ref_points=ref_pts,
            poly_auto_search=auto_search,
            parent=self
        )
        self._search_worker.progress_updated.connect(self._on_search_progress)
        self._search_worker.search_finished.connect(self._on_search_finished)
        self._search_worker.search_failed.connect(self._on_search_failed)
        self._search_worker.search_diagnostics.connect(self._on_search_diagnostics)
        self._search_worker.start()

    def _on_search_diagnostics(self, diag: dict):
        """静默缓存诊断信息，等用户导出计算书时一并写入"""
        self._last_search_diagnostics = diag
        # 状态栏一行提示
        total = diag.get("total_rejected", 0)
        mode = diag.get("mode", "")
        if total > 0:
            self.status_bar.showMessage(
                f"搜索诊断已记录 ({total} 次拒绝) — 见计算书「附录」"
            )
            
    def _on_search_finished(self, best_fs: float, best_params: list, info_msg: str):
        """寻优彻底完成后的结果处理 (智能识别圆弧参数与非圆弧折点)"""
        self.dock_search.btn_search.setEnabled(True)
        self.dock_search.btn_stop.setEnabled(False)
        self.dock_search.prog_bar.setValue(100)
        self.searched_best_params = best_params

        # 智能判别：如果最优解的第 1 项是列表或元组，代表返回的是非圆弧多段折点坐标
        if len(best_params) > 0 and isinstance(best_params[0], (list, tuple)):
            # 1. 非圆弧折线处理
            self.dock_search.lbl_best.setText(f"非圆弧最危险面: min Fs = {best_fs:.4f}")
            if hasattr(self.dock_search, "set_poly_points"):
                self.dock_search.set_poly_points(best_params)
        else:
            # 2. 传统圆弧参数处理: [Xc, Yc, R]
            bx = float(best_params[0])
            by = float(best_params[1])
            br = float(best_params[2])
            self.dock_search.lbl_best.setText(f"最危险滑弧: min Fs = {best_fs:.4f} (Xc={bx:.1f}, Yc={by:.1f}, R={br:.1f})")
            self.dock_search.set_circle_params(bx, by, br)

        self.on_params_changed()
        self.status_bar.showMessage(f"最危险滑面搜索完成: Fs = {best_fs:.4f}")

    def on_menu_export_report(self):
        """导出 Markdown 格式的计算书"""
        # 先确保当前切片是最新的
        self.on_params_changed()

        if not self.current_slices or not self.slice_info:
            QMessageBox.warning(self, "无法导出", "当前无有效切片数据，请先设置滑面并刷新。")
            return

        # 至少要跑过一次计算，否则结果表为空
        # 这里自动按当前选定模型跑一次，保证报告里有结果
        try:
            self.on_calculate_requested()
        except Exception:
            pass

        # 从界面取用户选择的求解模型名
        method_text = self.dock_search.get_selected_method_name()
        method_short = method_text.split()[0]  # 例如 "斯宾塞法"

        # 收集结果
        fs_current = None
        note_current = "—"
        try:
            # 从结果表读上一次的 FS
            row = self.dock_results.tbl_summary.rowCount()
            if row > 0:
                item = self.dock_results.tbl_summary.item(0, 1)
                if item and item.text() != "未收敛":
                    fs_current = float(item.text())
                item_note = self.dock_results.tbl_summary.item(0, 2)
                if item_note:
                    note_current = item_note.text()
        except Exception:
            pass

        solver_results = [(method_short, fs_current, note_current)]

        # 弹出保存对话框
        default_name = "计算书_" + datetime.now().strftime("%Y%m%d_%H%M") + ".md"
        fpath, _ = QFileDialog.getSaveFileName(
            self, "导出计算书 (Markdown)", default_name,
            "Markdown 文件 (*.md);;所有文件 (*.*)"
        )
        if not fpath:
            return
        if not fpath.lower().endswith(".md"):
            fpath += ".md"

        # 收集工程数据
        ground_pts   = self.dock_geom.get_ground_points()
        water_pts    = self.dock_geom.get_water_points()
        strata_lines = self.dock_geom.get_strata_lines()
        materials    = self.dock_mat.get_materials_list()
        surcharge    = self.dock_loads.get_surcharge_loads()
        kh           = self.dock_loads.get_seismic_kh()
        rain_depth   = self.dock_rain.get_current_wetting_front_depth()
        slip_surface = self.dock_search.get_slip_surface()
        _, _, _, n_slices = self.dock_search.get_circle_params()

        # 生成 markdown
        try:
            md_text = generate_report(
                project_name=self.windowTitle().split("(")[0].strip() or "未命名工程",
                ground_pts=ground_pts,
                water_pts=water_pts,
                strata_lines=strata_lines,
                materials=materials,
                surcharge_loads=surcharge,
                kh=kh,
                rainfall_depth=rain_depth,
                slip_surface=slip_surface,
                n_slices=n_slices,
                slices=self.current_slices,
                solver_results=solver_results,
                search_info=None,
                search_diagnostics=self._last_search_diagnostics,
            )

            with open(fpath, "w", encoding="utf-8") as f:
                f.write(md_text)

            self.status_bar.showMessage(f"计算书已导出: {os.path.basename(fpath)}")
            QMessageBox.information(
                self, "导出成功",
                f"计算书 (Markdown) 已成功导出：\n{fpath}\n\n"
                f"可以使用 Typora、VS Code、Obsidian 等工具打开，\n"
                f"或导出为 PDF。"
            )
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"生成计算书时发生异常:\n{e}")

    def on_search_stop_requested(self):
        if self._search_worker and self._search_worker.isRunning():
            self._search_worker.stop()
            self.status_bar.showMessage("正在终止后台寻优任务...")

    # ================= 边坡可靠度与失效概率评价逻辑 =================
    def on_reliability_requested(self):
        """响应'启动失效概率评价'"""
        self.on_params_changed()
        if not self.current_slices or not self.slice_info:
            QMessageBox.warning(self, "几何异常", "请先设置并确保滑面在边坡内部切出有效滑动体。")
            return

        cfg = self.dock_rel.get_config()
        ground_pts = self.dock_geom.get_ground_points()
        water_pts = self.dock_geom.get_water_points()
        strata_lines = self.dock_geom.get_strata_lines()
        materials = self.dock_mat.get_materials_list()
        surcharge = self.dock_loads.get_surcharge_loads()
        kh = self.dock_loads.get_seismic_kh()
        rain_depth = self.dock_rain.get_current_wetting_front_depth()
        xc, yc, R, _ = self.dock_search.get_circle_params()

        geom = SlopeGeometry(ground_pts, water_pts, strata_lines, surcharge)

        # 1. 点估计法 (PEM) 快速瞬时计算
        if cfg["method"] == "PEM":
            res = run_point_estimate_analysis(
                geom=geom,
                materials=materials,
                xc=xc, yc=yc, R=R,
                cov_c=cfg["cov_c"],
                cov_phi=cfg["cov_phi"],
                rho_c_phi=cfg["rho"],
                rainfall_depth=rain_depth,
                kh=kh
            )
            if res.get("success", False):
                self.dock_rel.display_results(res)
                self.status_bar.showMessage(f"点估计法计算完成: Pf = {res['pf_percent']:.2f}%, β = {res['beta']:.2f}")
            else:
                QMessageBox.warning(self, "计算失败", res.get("error", "点估计法计算未成功。"))

        # 2. 蒙特卡洛模拟法 (MCS) 异步多线程执行
        else:
            sim = MonteCarloSimulator(
                geom=geom,
                materials=materials,
                xc=xc, yc=yc, R=R,
                n_samples=cfg["n_samples"],
                eval_method=cfg["eval_method"],
                rainfall_depth=rain_depth,
                kh=kh,
                cov_c=cfg["cov_c"],
                dist_c=cfg["dist_c"],
                cov_phi=cfg["cov_phi"],
                dist_phi=cfg["dist_phi"],
                rho_c_phi=cfg["rho"],
                cov_gamma=cfg["cov_gamma"]
            )

            self.dock_rel.btn_run_rel.setEnabled(False)
            self.dock_rel.btn_stop_rel.setEnabled(True)
            self.dock_rel.prog_bar.setValue(0)
            self.status_bar.showMessage(f"正在执行蒙特卡洛抽样模拟 ({cfg['n_samples']} 次)...")

            self._reliability_worker = ReliabilityWorker(sim, parent=self)
            self._reliability_worker.progress_updated.connect(self._on_rel_progress)
            self._reliability_worker.reliability_finished.connect(self._on_rel_finished)
            self._reliability_worker.reliability_failed.connect(self._on_rel_failed)
            self._reliability_worker.start()

    def on_reliability_stop_requested(self):
        """响应用户点击'终止评价'"""
        if hasattr(self, "_reliability_worker") and self._reliability_worker and self._reliability_worker.isRunning():
            self._reliability_worker.stop()
            self.status_bar.showMessage("正在终止可靠度抽样计算...")

    def _on_rel_progress(self, current: int, total: int, current_pf: float):
        """后台抽样进度实时更新"""
        pct = int(current / max(1, total) * 100)
        self.dock_rel.prog_bar.setValue(min(100, pct))
        self.dock_rel.lbl_pf.setText(f"{current_pf:.2f}% (抽样中...)")

    def _on_rel_finished(self, res: dict):
        """模拟计算正常完成"""
        self.dock_rel.btn_run_rel.setEnabled(True)
        self.dock_rel.btn_stop_rel.setEnabled(False)
        self.dock_rel.prog_bar.setValue(100)
        self.dock_rel.display_results(res)
        self.status_bar.showMessage(f"蒙特卡洛评价完成: Pf = {res['pf_percent']:.2f}%, β = {res['beta']:.3f}")

    def _on_rel_failed(self, err_msg: str):
        """模拟失败或用户主动终止"""
        self.dock_rel.btn_run_rel.setEnabled(True)
        self.dock_rel.btn_stop_rel.setEnabled(False)
        self.status_bar.showMessage(err_msg)
        QMessageBox.information(self, "可靠度评价提示", err_msg)

    def _on_search_progress(self, current: int, total: int, current_best: float):
        """【寻优过程中的实时进度更新】入参只有 current, total, current_best"""
        pct = int(current / max(1, total) * 100)
        self.dock_search.prog_bar.setValue(min(100, pct))
        self.dock_search.lbl_best.setText(f"寻优中... 当前最小 Fs = {current_best:.4f}")

    def _on_search_failed(self, err_msg: str):
        self.dock_search.btn_search.setEnabled(True)
        self.dock_search.btn_stop.setEnabled(False)
        self.status_bar.showMessage(err_msg)
        QMessageBox.information(self, "搜索提示", err_msg)

    def on_apply_searched_circle(self):
        if self.searched_best_params is None:
            QMessageBox.information(self, "提示", "请先启动搜索获得最危险滑面。")
            return

        p = self.searched_best_params

        # ---------- 非圆弧折线 ----------
        if len(p) > 0 and isinstance(p[0], (list, tuple)):
            try:
                points = [(float(a), float(b)) for a, b in p]
            except (TypeError, ValueError, IndexError) as e:
                QMessageBox.warning(self, "警告", f"折线点解析失败: {p} ({e})")
                return

            # 你已经在 _on_search_finished 里调过 set_poly_points，
            # 这里再调一次以确保模型同步
            if hasattr(self.dock_search, "set_poly_points"):
                self.dock_search.set_poly_points(points)
            else:
                QMessageBox.warning(self, "警告", "当前面板不支持非圆弧折线滑面。")
                return

            self.on_params_changed()
            QMessageBox.information(
                self, "应用成功",
                "已成功载入非圆弧最危险折线滑面：\n" +
                "\n".join(f"  ({x:.2f}, {y:.2f})" for x, y in points)
            )
            return

        # ---------- 圆弧 ----------
        if len(p) < 3:
            QMessageBox.warning(self, "警告", f"圆弧参数异常: {p}")
            return

        try:
            bx, by, br = float(p[0]), float(p[1]), float(p[2])
        except (TypeError, ValueError) as e:
            QMessageBox.warning(self, "警告", f"圆弧参数解析失败: {p} ({e})")
            return

        self.dock_search.set_circle_params(bx, by, br)
        self.on_params_changed()
        self.on_calculate_requested()
        QMessageBox.information(
            self, "应用成功",
            f"已成功载入最危险滑弧：\nXc={bx:.2f} m, Yc={by:.2f} m, R={br:.2f} m\n"
            f"已自动完成 5 种经典 LEM 模型复核。"
        )

    def on_menu_new(self):
        # 恢复默认几何
        self._last_search_diagnostics = None
        default_ground = [(0.0, 15.0), (20.0, 15.0), (35.0, 0.0), (60.0, 0.0)]
        default_water  = [(0.0, 12.0), (20.0, 12.0), (35.0, -1.0), (60.0, -1.0)]
        default_strata = [[(-10.0, 6.0), (70.0, 6.0)]]

        self.dock_geom.from_dict({
            "ground": default_ground,
            "water": default_water,
            "strata": default_strata,
        })

        # 恢复默认材料
        self.dock_mat.from_dict({
            "active_regime": 0,
            "current_layer": 0,
            "layers": [
                {"name": "第1层-上覆土", "gamma_dry": 19.0, "gamma_sat": 21.0,
                "c_prime": 15.0, "phi_deg": 20.0, "is_unsaturated": False,
                "phi_b_deg": 15.0, "suction_cutoff": 100.0},
                {"name": "第2层-下卧土", "gamma_dry": 22.0, "gamma_sat": 23.5,
                "c_prime": 40.0, "phi_deg": 30.0, "is_unsaturated": False,
                "phi_b_deg": 22.0, "suction_cutoff": 150.0},
                {"name": "第3层-基岩层", "gamma_dry": 25.0, "gamma_sat": 26.0,
                "c_prime": 80.0, "phi_deg": 38.0, "is_unsaturated": False,
                "phi_b_deg": 28.0, "suction_cutoff": 200.0},
            ],
        })

        # 恢复默认滑面参数
        self.dock_search.from_dict({
            "surface_type": "circular",
            "circle": {"xc": 25.0, "yc": 22.0, "R": 23.0, "n_slices": 30},
            "polygon": [(12.0, 15.0), (25.0, 4.0), (38.0, 0.0)],
        })

        # 恢复环境
        self.dock_loads.from_dict({"q": 0.0, "x1": 5.0, "x2": 18.0, "kh": 0.0})
        self.dock_rain.from_dict({
            "series": [(0.0, 10.0), (12.0, 35.0), (24.0, 60.0), (48.0, 5.0)],
            "ks_mm_h": 15.0, "delta_theta": 0.20, "current_time": 0,
        })

        self.current_project_file = None
        self.searched_best_params = None

        self.on_params_changed()
        self.canvas.fit_view_to_slope(margin_ratio=0.15)
        self.status_bar.showMessage("已新建工程并恢复默认参数。")

    def on_menu_open(self):
        fpath, _ = QFileDialog.getOpenFileName(
            self, "打开工程文件", "",
            "LEM 工程文件 (*.lem *.json);;所有文件 (*.*)"
        )
        if not fpath:
            return

        data = load_project_file(fpath)
        if not data:
            QMessageBox.critical(self, "打开失败", "工程文件损坏或格式不正确。")
            return

        try:
            # 兼容 v1：旧格式是平铺的 ground_points / water_points / circle
            if data.get("version", 1) == 1:
                data = self._migrate_v1_to_v2(data)

            if "geometry" in data:
                self.dock_geom.from_dict(data["geometry"])
            if "materials" in data:
                self.dock_mat.from_dict(data["materials"])
            if "environment" in data:
                env = data["environment"]
                self.dock_loads.from_dict(env)
                if "rainfall" in env:
                    self.dock_rain.from_dict(env["rainfall"])
            if "slip_surface" in data:
                self.dock_search.from_dict(data["slip_surface"])
            if "reliability" in data:
                self.dock_rel.from_dict(data["reliability"])

            self.current_project_file = fpath

            # 刷新全部视图
            self.on_params_changed()
            self.canvas.fit_view_to_slope(margin_ratio=0.15)
            self.status_bar.showMessage(f"已成功载入工程: {os.path.basename(fpath)}")

        except Exception as e:
            QMessageBox.critical(self, "打开失败", f"载入过程发生异常:\n{e}")


    def _migrate_v1_to_v2(self, old: dict) -> dict:
        """把 v1 旧格式迁移到 v2 结构"""
        new = {"version": 2, "app": old.get("app", "unknown")}
        new["geometry"] = {
            "ground": old.get("ground_points", []),
            "water": old.get("water_points", None),
            "strata": old.get("strata_lines", []),
        }
        c = old.get("circle", {})
        new["slip_surface"] = {
            "surface_type": "circular",
            "circle": {
                "xc": c.get("xc", 25.0),
                "yc": c.get("yc", 22.0),
                "R": c.get("R", 23.0),
                "n_slices": 30,
            },
            "polygon": [],
        }
        return new

    def on_menu_save(self):
        if self.current_project_file:
            self._save_to_path(self.current_project_file)
        else:
            self.on_menu_save_as()


    def on_menu_save_as(self):
        fpath, _ = QFileDialog.getSaveFileName(
            self, "工程另存为", "slope_case.lem",
            "LEM 工程文件 (*.lem *.json);;所有文件 (*.*)"
        )
        if not fpath:
            return
        self._save_to_path(fpath)
        
        
    def _save_to_path(self, fpath: str):
        """统一的保存实现"""
        data = {
            "geometry": self.dock_geom.to_dict(),
            "materials": self.dock_mat.to_dict(),
            "environment": {
                **self.dock_loads.to_dict(),
                "rainfall": self.dock_rain.to_dict(),
            },
            "slip_surface": self.dock_search.to_dict(),
            "reliability": self.dock_rel.to_dict(),
        }
        if save_project_file(fpath, data):
            self.current_project_file = fpath
            self.status_bar.showMessage(f"工程已保存: {os.path.basename(fpath)}")
        else:
            QMessageBox.critical(self, "保存失败", "写入文件发生错误。")
        
        
    def on_menu_import_dxf(self):
        fpath, _ = QFileDialog.getOpenFileName(self, "导入 CAD DXF 地表线", "", "AutoCAD DXF 文件 (*.dxf);;所有文件 (*.*)")
        if not fpath:
            return
        pts = import_dxf_polyline(fpath)
        if len(pts) >= 2:
            self.dock_geom.data_ground = pts
            self.dock_geom.tree.setCurrentItem(self.dock_geom.item_ground)
            self.dock_geom._load_table_data(pts)
            self.on_params_changed()
            self.canvas.fit_view_to_slope()
            self.status_bar.showMessage(f"成功从 DXF 导入 {len(pts)} 个地表顶点。")
            QMessageBox.information(self, "导入成功", f"已从 DXF 提取并载入 {len(pts)} 个连续地表坐标点。")
        else:
            QMessageBox.warning(self, "导入失败", "未在 DXF 文件中找到有效的连续折线或线段实体。")

    def on_menu_export_dxf(self):
        fpath, _ = QFileDialog.getSaveFileName(self, "分图层导出模型至 CAD DXF", "slope_geometry.dxf", "AutoCAD DXF 文件 (*.dxf);;所有文件 (*.*)")
        if not fpath:
            return

        ground_pts = self.dock_geom.get_ground_points()
        strata_lines = self.dock_geom.get_strata_lines()
        water_pts = self.dock_geom.get_water_points()

        ok = export_model_dxf(
            filepath=fpath,
            ground_pts=ground_pts,
            strata_lines=strata_lines,
            water_pts=water_pts
        )
        if ok:
            self.status_bar.showMessage(f"模型已成功分图层导出为 DXF: {os.path.basename(fpath)}")
            QMessageBox.information(self, "导出成功", f"分图层 CAD DXF 导出完成：\n{fpath}\n包含 0_GROUND_SURFACE、1_STRATA_LAYER 与 2_PHREATIC_WATER 图层。")
        else:
            QMessageBox.critical(self, "导出失败", "DXF 文件写出发生错误。")

    def on_menu_export_csv(self):
        if not self.current_slices:
            QMessageBox.warning(self, "提示", "当前无有效切片数据可导出。")
            return

        fpath, _ = QFileDialog.getSaveFileName(self, "导出切片数据报表", "slope_slices_report.csv", "CSV 逗号分隔文件 (*.csv);;所有文件 (*.*)")
        if not fpath:
            return

        try:
            with open(fpath, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "土条号", "所属地层", "中点X(m)", "条宽b(m)", "高度h(m)",
                    "土自重(kN)", "附加外载(kN)", "总竖力W(kN)", "地震力Fh(kN)",
                    "孔压u(kPa)", "基质吸力(kPa)", "总黏聚力(kPa)", "摩擦角(度)", "底坡角(度)", "底斜长(m)"
                ])
                for s in self.current_slices:
                    writer.writerow([
                        s.index, s.layer_name, round(s.xm, 3), round(s.b, 3), round(s.h, 3),
                        round(s.W_soil, 3), round(s.q_load, 3), round(s.W, 3), round(s.Fh, 3),
                        round(s.u, 3), round(s.suction, 3), round(s.c, 3),
                        round(float(np.degrees(s.phi)), 3),
                        round(float(np.degrees(s.alpha)), 3),
                        round(s.l, 3)
                    ])
            self.status_bar.showMessage(f"切片数据报表已导出: {os.path.basename(fpath)}")
            QMessageBox.information(self, "导出成功", f"已成功将 {len(self.current_slices)} 个土条的完整数据导出至 CSV。")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"写入 CSV 报表时出错: {str(e)}")

    def on_menu_theory_help(self):
        text = (
            "<h3>极限平衡法 (LEM) 理论模型体系说明</h3>"
            "<p>本软件实现了土力学经典的 5 大极限平衡计算模型，全面支持任意多层起伏地层、地下水浸润线、动态降雨时变入渗、非饱和吸力本构及地震拟静力荷载：</p>"
            "<ul>"
            "<li><b>Fellenius (瑞典条分法)</b>：力矩平衡显式解，适用于均质土初筛。</li>"
            "<li><b>Simplified Bishop (简化毕肖普法)</b>：考虑水平条间力，满足竖向力和力矩平衡。</li>"
            "<li><b>Simplified Janbu (简化让布法)</b>：满足条块力平衡，结合 d/L 引入 f0 经验修正。</li>"
            "<li><b>Spencer (斯宾塞法)</b>：完全平衡严密法，联立求解 (Fs, θ)。</li>"
            "<li><b>Morgenstern-Price (M-P 法 / GLE)</b>：广义严密极限平衡法，条间剪力假定为 X = λ·f(x)·E（半正弦波），求解 (Fs, λ)。</li>"
            "</ul>"
        )
        QMessageBox.about(self, "理论说明", text)

    def on_menu_about(self):
        text = (
            "<h3>边坡极限平衡法稳定性分析平台 (LEM-Slope-Studio)</h3>"
            "<p>基于 Python 3 与 PyQt5 架构开发，采用专业 QDockWidget 模块化界面布局。</p>"
            "<p>内置经典 LEM 模型、全局优化寻优算法、动态降雨历时入渗分析及分图层 AutoCAD DXF 交换。</p>"
        )
        QMessageBox.about(self, "关于系统", text)