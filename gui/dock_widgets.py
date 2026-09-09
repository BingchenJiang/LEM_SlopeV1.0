# -*- coding: utf-8 -*-
"""
专业 CAD/CAE 风格的可拆卸与浮动停靠窗口模块 (PyQt5 QDockWidget)
支持图标与文本一体化工程控件
"""
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
from PyQt5.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QDoubleSpinBox, QSpinBox, QComboBox, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
    QProgressBar, QCheckBox, QTreeWidget, QTreeWidgetItem, QSlider
)
from PyQt5.QtCore import Qt, pyqtSignal

from core.materials import SoilMaterial
from core.rainfall import RainfallTimeSeries
from core.slicing import Slice
from gui.icons import get_icon


class GeometryDockWidget(QDockWidget):
    """地层树与任意多段线几何拓扑管理停靠窗"""
    geometry_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("模型几何与地层分界", parent)
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self._init_ui()

    def _init_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)

        layout.addWidget(QLabel("<b>几何实体与地层图层树:</b>"))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["图层实体名称", "控制点数"])
        
        self.item_ground = QTreeWidgetItem(["地表轮廓线", "4"])
        self.item_water = QTreeWidgetItem(["地下水浸润线", "4"])
        self.item_strata_root = QTreeWidgetItem(["地层分界面 (任意起伏)", "1"])
        
        self.tree.addTopLevelItem(self.item_ground)
        self.tree.addTopLevelItem(self.item_water)
        self.tree.addTopLevelItem(self.item_strata_root)
        
        self.item_layer1 = QTreeWidgetItem(["第1分界面 (土层1/2界面)", "2"])
        self.item_strata_root.addChild(self.item_layer1)
        self.item_strata_root.setExpanded(True)
        
        self.tree.currentItemChanged.connect(self._on_tree_selection_changed)
        layout.addWidget(self.tree, stretch=2)

        h_btn_strata = QHBoxLayout()
        btn_add_strata = QPushButton("新建地层分界")
        btn_add_strata.setIcon(get_icon("add_item"))
        btn_add_strata.clicked.connect(self._add_strata_line)

        btn_del_strata = QPushButton("删除当前地层")
        btn_del_strata.setIcon(get_icon("del_item"))
        btn_del_strata.clicked.connect(self._del_strata_line)

        h_btn_strata.addWidget(btn_add_strata)
        h_btn_strata.addWidget(btn_del_strata)
        layout.addLayout(h_btn_strata)

        self.lbl_table_title = QLabel("<b>地表轮廓线控制点 (X, Y 单位: 米):</b>")
        layout.addWidget(self.lbl_table_title)

        self.tbl_coords = QTableWidget(4, 2)
        self.tbl_coords.setHorizontalHeaderLabels(["X 坐标 (m)", "Y 高程 (m)"])
        self.tbl_coords.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tbl_coords, stretch=3)

        h_btn_pts = QHBoxLayout()
        btn_add_pt = QPushButton("添加坐标点")
        btn_add_pt.setIcon(get_icon("add_item"))
        btn_add_pt.clicked.connect(self._add_point)

        btn_del_pt = QPushButton("删除选中点")
        btn_del_pt.setIcon(get_icon("del_item"))
        btn_del_pt.clicked.connect(self._del_point)

        h_btn_pts.addWidget(btn_add_pt)
        h_btn_pts.addWidget(btn_del_pt)
        layout.addLayout(h_btn_pts)

        btn_apply_geom = QPushButton("刷新几何模型")
        btn_apply_geom.setIcon(get_icon("refresh"))
        btn_apply_geom.clicked.connect(self._save_current_table_and_notify)
        layout.addWidget(btn_apply_geom)

        self.setWidget(container)

        self.data_ground = [(0.0, 15.0), (20.0, 15.0), (35.0, 0.0), (60.0, 0.0)]
        self.data_water = [(0.0, 12.0), (20.0, 12.0), (35.0, -1.0), (60.0, -1.0)]
        self.data_strata = [[(-10.0, 6.0), (70.0, 6.0)]]
        self.current_editing_key = "ground"
        self._load_table_data(self.data_ground)

    def _on_tree_selection_changed(self, current, previous):
        if not current:
            return
        self._save_current_table_data()
        
        text = current.text(0)
        if text == "地表轮廓线":
            self.current_editing_key = "ground"
            self.lbl_table_title.setText("<b>地表轮廓线控制点 (X, Y 单位: 米):</b>")
            self._load_table_data(self.data_ground)
        elif text == "地下水浸润线":
            self.current_editing_key = "water"
            self.lbl_table_title.setText("<b>地下水浸润线控制点 (X, Y 单位: 米):</b>")
            self._load_table_data(self.data_water)
        elif "分界面" in text and current.parent() == self.item_strata_root:
            idx = self.item_strata_root.indexOfChild(current)
            self.current_editing_key = f"strata_{idx}"
            self.lbl_table_title.setText(f"<b>{text}控制点 (X, Y 单位: 米):</b>")
            if idx < len(self.data_strata):
                self._load_table_data(self.data_strata[idx])

    def _save_current_table_data(self):
        pts = []
        for r in range(self.tbl_coords.rowCount()):
            ix = self.tbl_coords.item(r, 0)
            iy = self.tbl_coords.item(r, 1)
            if ix and iy:
                try:
                    pts.append((float(ix.text()), float(iy.text())))
                except ValueError:
                    pass
        if len(pts) >= 2:
            pts = sorted(pts, key=lambda p: p[0])
            if self.current_editing_key == "ground":
                self.data_ground = pts
                self.item_ground.setText(1, str(len(pts)))
            elif self.current_editing_key == "water":
                self.data_water = pts
                self.item_water.setText(1, str(len(pts)))
            elif self.current_editing_key.startswith("strata_"):
                idx = int(self.current_editing_key.split("_")[1])
                if idx < len(self.data_strata):
                    self.data_strata[idx] = pts
                    child = self.item_strata_root.child(idx)
                    if child:
                        child.setText(1, str(len(pts)))

    def _load_table_data(self, pts):
        self.tbl_coords.setRowCount(len(pts))
        for r, (x, y) in enumerate(pts):
            self.tbl_coords.setItem(r, 0, QTableWidgetItem(str(round(x, 3))))
            self.tbl_coords.setItem(r, 1, QTableWidgetItem(str(round(y, 3))))

    def _add_point(self):
        row = self.tbl_coords.rowCount()
        self.tbl_coords.insertRow(row)
        self.tbl_coords.setItem(row, 0, QTableWidgetItem("0.0"))
        self.tbl_coords.setItem(row, 1, QTableWidgetItem("0.0"))

    def _del_point(self):
        r = self.tbl_coords.currentRow()
        if r >= 0 and self.tbl_coords.rowCount() > 2:
            self.tbl_coords.removeRow(r)

    def _add_strata_line(self):
        self._save_current_table_data()
        new_idx = len(self.data_strata)
        default_y = 6.0 - new_idx * 4.0
        new_line = [(-10.0, default_y), (70.0, default_y)]
        self.data_strata.append(new_line)
        
        item = QTreeWidgetItem([f"第{new_idx + 1}分界面", "2"])
        self.item_strata_root.addChild(item)
        self.item_strata_root.setText(1, str(len(self.data_strata)))
        self.tree.setCurrentItem(item)
        self.geometry_changed.emit()

    def _del_strata_line(self):
        curr = self.tree.currentItem()
        if curr and curr.parent() == self.item_strata_root and len(self.data_strata) > 0:
            idx = self.item_strata_root.indexOfChild(curr)
            self.data_strata.pop(idx)
            self.item_strata_root.removeChild(curr)
            self.item_strata_root.setText(1, str(len(self.data_strata)))
            self.tree.setCurrentItem(self.item_ground)
            self.geometry_changed.emit()

    def _save_current_table_and_notify(self):
        self._save_current_table_data()
        self.geometry_changed.emit()

    def get_ground_points(self) -> List[Tuple[float, float]]:
        self._save_current_table_data()
        return self.data_ground

    def get_water_points(self) -> Optional[List[Tuple[float, float]]]:
        self._save_current_table_data()
        return self.data_water

    def get_strata_lines(self) -> List[List[Tuple[float, float]]]:
        self._save_current_table_data()
        return self.data_strata


class MaterialDockWidget(QDockWidget):
    """饱和/非饱和工况区分与多层土材料库停靠窗"""
    materials_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("物理力学参数与本构模型", parent)
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self._init_ui()

    def _init_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)

        grp_regime = QGroupBox("力学分析工况与本构模式")
        form_regime = QFormLayout()
        self.combo_regime = QComboBox()
        self.combo_regime.addItems([
            "常规有效应力模式 (饱和/天然工况)",
            "非饱和吸力强度模式 (Fredlund 双应力准则)"
        ])
        self.combo_regime.currentIndexChanged.connect(self._on_regime_changed)
        form_regime.addRow("分析工况:", self.combo_regime)
        grp_regime.setLayout(form_regime)
        layout.addWidget(grp_regime)

        grp_mat = QGroupBox("土层材料力学属性库")
        form_mat = QFormLayout()

        self.combo_layer = QComboBox()
        self.combo_layer.addItems(["第 1 层 (上部土体)", "第 2 层 (下卧地层)", "第 3 层 (基岩层)"])
        self.combo_layer.currentIndexChanged.connect(self._on_layer_selected)
        form_mat.addRow("当前配置土层:", self.combo_layer)

        self.spin_gamma_dry = QDoubleSpinBox(); self.spin_gamma_dry.setRange(5.0, 40.0); self.spin_gamma_dry.setValue(19.0); self.spin_gamma_dry.setSuffix(" kN/m3")
        self.spin_gamma_sat = QDoubleSpinBox(); self.spin_gamma_sat.setRange(5.0, 40.0); self.spin_gamma_sat.setValue(21.0); self.spin_gamma_sat.setSuffix(" kN/m3")
        self.spin_c = QDoubleSpinBox(); self.spin_c.setRange(0.0, 500.0); self.spin_c.setValue(15.0); self.spin_c.setSuffix(" kPa")
        self.spin_phi = QDoubleSpinBox(); self.spin_phi.setRange(0.0, 55.0); self.spin_phi.setValue(20.0); self.spin_phi.setSuffix(" °")

        form_mat.addRow("天然重度 (γ):", self.spin_gamma_dry)
        form_mat.addRow("饱和重度 (γsat):", self.spin_gamma_sat)
        form_mat.addRow("有效黏聚力 (c'):", self.spin_c)
        form_mat.addRow("有效摩擦角 (φ'):", self.spin_phi)

        self.grp_unsat = QGroupBox("非饱和基质吸力强度参数")
        form_unsat = QFormLayout()
        self.spin_phib = QDoubleSpinBox(); self.spin_phib.setRange(0.0, 50.0); self.spin_phib.setValue(15.0); self.spin_phib.setSuffix(" °")
        self.spin_cutoff = QDoubleSpinBox(); self.spin_cutoff.setRange(0.0, 1000.0); self.spin_cutoff.setValue(100.0); self.spin_cutoff.setSuffix(" kPa")
        form_unsat.addRow("吸力摩擦角 (φb):", self.spin_phib)
        form_unsat.addRow("吸力截断上限值:", self.spin_cutoff)
        self.grp_unsat.setLayout(form_unsat)
        self.grp_unsat.setEnabled(False)

        form_mat.addRow(self.grp_unsat)
        grp_mat.setLayout(form_mat)
        layout.addWidget(grp_mat)

        btn_save_mat = QPushButton("保存并应用土层参数")
        btn_save_mat.setIcon(get_icon("apply_surface"))
        btn_save_mat.clicked.connect(self._save_current_layer_params)
        layout.addWidget(btn_save_mat)

        layout.addStretch()
        self.setWidget(container)

        self.materials_db = [
            SoilMaterial("第1层-上覆土", 19.0, 21.0, 15.0, 20.0, False, 15.0, 100.0),
            SoilMaterial("第2层-下卧土", 22.0, 23.5, 40.0, 30.0, False, 22.0, 150.0),
            SoilMaterial("第3层-基岩层", 25.0, 26.0, 80.0, 38.0, False, 28.0, 200.0),
        ]
        self._load_layer_params(0)

    def _on_regime_changed(self, idx):
        is_unsat = (idx == 1)
        self.grp_unsat.setEnabled(is_unsat)
        for m in self.materials_db:
            m.is_unsaturated = is_unsat
        self.materials_changed.emit()

    def _on_layer_selected(self, idx):
        if 0 <= idx < len(self.materials_db):
            self._load_layer_params(idx)

    def _load_layer_params(self, idx):
        m = self.materials_db[idx]
        self.spin_gamma_dry.setValue(m.gamma_dry)
        self.spin_gamma_sat.setValue(m.gamma_sat)
        self.spin_c.setValue(m.c_prime)
        self.spin_phi.setValue(m.phi_deg)
        self.spin_phib.setValue(m.phi_b_deg)
        self.spin_cutoff.setValue(m.suction_cutoff)

    def _save_current_layer_params(self):
        idx = self.combo_layer.currentIndex()
        if 0 <= idx < len(self.materials_db):
            is_unsat = (self.combo_regime.currentIndex() == 1)
            self.materials_db[idx] = SoilMaterial(
                name=self.combo_layer.currentText(),
                gamma_dry=self.spin_gamma_dry.value(),
                gamma_sat=self.spin_gamma_sat.value(),
                c_prime=self.spin_c.value(),
                phi_deg=self.spin_phi.value(),
                is_unsaturated=is_unsat,
                phi_b_deg=self.spin_phib.value(),
                suction_cutoff=self.spin_cutoff.value()
            )
            self.materials_changed.emit()

    def get_materials_list(self) -> List[SoilMaterial]:
        return self.materials_db


class RainfallDockWidget(QDockWidget):
    """动态时序降雨过程与时间轴控制停靠窗"""
    time_step_changed = pyqtSignal(float)
    solve_time_series_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("动态时序降雨与入渗时间轴", parent)
        self.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self._init_ui()

    def _init_ui(self):
        container = QWidget()
        layout = QHBoxLayout(container)

        grp_hyeto = QGroupBox("降雨强度-历时过程线 (Hyetograph)")
        v_h = QVBoxLayout(grp_hyeto)
        self.tbl_rain = QTableWidget(4, 2)
        self.tbl_rain.setHorizontalHeaderLabels(["历时时刻 (h)", "降雨强度 (mm/h)"])
        self.tbl_rain.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        default_hyeto = [(0.0, 10.0), (12.0, 35.0), (24.0, 60.0), (48.0, 5.0)]
        for r, (t, i_val) in enumerate(default_hyeto):
            self.tbl_rain.setItem(r, 0, QTableWidgetItem(str(t)))
            self.tbl_rain.setItem(r, 1, QTableWidgetItem(str(i_val)))
        v_h.addWidget(self.tbl_rain)
        layout.addWidget(grp_hyeto, stretch=3)

        grp_slider = QGroupBox("时变入渗求解与时间轴控制")
        v_s = QVBoxLayout(grp_slider)

        f_infil = QFormLayout()
        self.spin_ks = QDoubleSpinBox(); self.spin_ks.setValue(15.0); self.spin_ks.setSuffix(" mm/h")
        self.spin_theta = QDoubleSpinBox(); self.spin_theta.setValue(0.20); self.spin_theta.setSingleStep(0.05)
        f_infil.addRow("饱和渗透系数 (Ks):", self.spin_ks)
        f_infil.addRow("有效储水空隙增量 (Δθ):", self.spin_theta)
        v_s.addLayout(f_infil)

        self.slider_time = QSlider(Qt.Horizontal)
        self.slider_time.setRange(0, 48)
        self.slider_time.setValue(0)
        self.slider_time.valueChanged.connect(self._on_slider_moved)
        v_s.addWidget(self.slider_time)

        h_info = QHBoxLayout()
        self.lbl_time_val = QLabel("当前分析时刻: t = 0.0 h")
        self.lbl_time_val.setStyleSheet("font-weight: bold; color: #2980b9;")
        self.lbl_wet_depth = QLabel("计算湿润锋深度: zf = 0.00 m")
        self.lbl_wet_depth.setStyleSheet("font-weight: bold; color: #c0392b;")
        h_info.addWidget(self.lbl_time_val)
        h_info.addWidget(self.lbl_wet_depth)
        v_s.addLayout(h_info)

        btn_run_series = QPushButton("计算降雨全历时稳定性衰减曲线 Fs(t)")
        btn_run_series.setIcon(get_icon("rainfall_time"))
        btn_run_series.setStyleSheet("padding: 6px; font-weight: bold;")
        btn_run_series.clicked.connect(self.solve_time_series_requested.emit)
        v_s.addWidget(btn_run_series)

        layout.addWidget(grp_slider, stretch=4)
        self.setWidget(container)

    def _get_time_series_data(self) -> List[Tuple[float, float]]:
        series = []
        for r in range(self.tbl_rain.rowCount()):
            it = self.tbl_rain.item(r, 0)
            ii = self.tbl_rain.item(r, 1)
            if it and ii:
                try:
                    series.append((float(it.text()), float(ii.text())))
                except ValueError:
                    pass
        return sorted(series, key=lambda x: x[0]) if series else [(0.0, 0.0)]

    def get_rainfall_model(self) -> RainfallTimeSeries:
        series = self._get_time_series_data()
        return RainfallTimeSeries(series, self.spin_ks.value(), self.spin_theta.value())

    def _on_slider_moved(self, val):
        t_current = float(val)
        model = self.get_rainfall_model()
        depth = model.get_wetting_front_depth(t_current)
        self.lbl_time_val.setText(f"当前分析时刻: t = {t_current:.1f} h")
        self.lbl_wet_depth.setText(f"计算湿润锋深度: zf = {depth:.2f} m")
        self.time_step_changed.emit(t_current)

    def get_current_wetting_front_depth(self) -> float:
        t_current = float(self.slider_time.value())
        model = self.get_rainfall_model()
        return model.get_wetting_front_depth(t_current)


class LoadsDockWidget(QDockWidget):
    """荷载与抗震拟静力分析停靠窗"""
    loads_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("外荷载与抗震工况", parent)
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self._init_ui()

    def _init_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)

        grp_load = QGroupBox("坡顶附加荷载")
        form_load = QFormLayout()
        self.spin_q = QDoubleSpinBox(); self.spin_q.setRange(0.0, 500.0); self.spin_q.setValue(0.0); self.spin_q.setSuffix(" kPa")
        self.spin_qx1 = QDoubleSpinBox(); self.spin_qx1.setRange(-50, 100); self.spin_qx1.setValue(5.0); self.spin_qx1.setSuffix(" m")
        self.spin_qx2 = QDoubleSpinBox(); self.spin_qx2.setRange(-50, 100); self.spin_qx2.setValue(18.0); self.spin_qx2.setSuffix(" m")
        form_load.addRow("荷载强度 (q):", self.spin_q)
        form_load.addRow("分布起点 X1:", self.spin_qx1)
        form_load.addRow("分布终点 X2:", self.spin_qx2)
        grp_load.setLayout(form_load)
        layout.addWidget(grp_load)

        grp_seismic = QGroupBox("拟静力法地震惯性力")
        form_seismic = QFormLayout()
        self.spin_kh = QDoubleSpinBox(); self.spin_kh.setRange(0.0, 0.4); self.spin_kh.setValue(0.0); self.spin_kh.setSingleStep(0.02)
        form_seismic.addRow("水平地震力系数 (kh):", self.spin_kh)
        grp_seismic.setLayout(form_seismic)
        layout.addWidget(grp_seismic)

        btn_apply = QPushButton("应用荷载设置")
        btn_apply.setIcon(get_icon("apply_surface"))
        btn_apply.clicked.connect(self.loads_changed.emit)
        layout.addWidget(btn_apply)

        layout.addStretch()
        self.setWidget(container)

    def get_surcharge_loads(self) -> List[Tuple[float, float, float]]:
        q = self.spin_q.value()
        if q > 0:
            return [(self.spin_qx1.value(), self.spin_qx2.value(), q)]
        return []

    def get_seismic_kh(self) -> float:
        return self.spin_kh.value()


class SearchDockWidget(QDockWidget):
    """滑面寻优与求解控制停靠窗"""
    calculate_requested = pyqtSignal()
    search_requested = pyqtSignal()
    search_stop_requested = pyqtSignal()
    apply_searched_circle = pyqtSignal()
    preview_circle_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("滑弧求解与全局智能寻优", parent)
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self._init_ui()

    def _init_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)

        grp_circle = QGroupBox("指定试算滑弧参数")
        form_circle = QFormLayout()
        self.spin_xc = QDoubleSpinBox(); self.spin_xc.setRange(-200.0, 200.0); self.spin_xc.setValue(25.0); self.spin_xc.setSuffix(" m")
        self.spin_yc = QDoubleSpinBox(); self.spin_yc.setRange(-200.0, 200.0); self.spin_yc.setValue(22.0); self.spin_yc.setSuffix(" m")
        self.spin_r = QDoubleSpinBox(); self.spin_r.setRange(1.0, 300.0); self.spin_r.setValue(23.0); self.spin_r.setSuffix(" m")
        self.spin_slices = QSpinBox(); self.spin_slices.setRange(10, 150); self.spin_slices.setValue(30); self.spin_slices.setSuffix(" 个")
        form_circle.addRow("滑弧圆心 Xc:", self.spin_xc)
        form_circle.addRow("滑弧圆心 Yc:", self.spin_yc)
        form_circle.addRow("滑弧半径 R:", self.spin_r)
        form_circle.addRow("切片土条数 N:", self.spin_slices)
        grp_circle.setLayout(form_circle)
        layout.addWidget(grp_circle)

        btn_preview = QPushButton("预览指定滑面网格")
        btn_preview.setIcon(get_icon("refresh"))
        btn_preview.clicked.connect(self.preview_circle_changed.emit)
        layout.addWidget(btn_preview)

        grp_algo = QGroupBox("临界最危险滑面全局寻优")
        form_algo = QFormLayout()
        self.combo_algo = QComboBox()
        self.combo_algo.addItems([
            "粒子群优化算法 (PSO)",
            "模拟退火算法 (Simulated Annealing)",
            "差分进化算法 (Differential Evolution)",
            "单纯形搜索法 (Nelder-Mead)",
            "传统网格扫描法 (Grid Search)"
        ])
        self.combo_eval = QComboBox()
        self.combo_eval.addItems(["Simplified Bishop (推荐/高效)", "Fellenius / Ordinary"])
        form_algo.addRow("寻优算法:", self.combo_algo)
        form_algo.addRow("目标模型:", self.combo_eval)

        self.spin_xmin = QDoubleSpinBox(); self.spin_xmin.setValue(10.0)
        self.spin_xmax = QDoubleSpinBox(); self.spin_xmax.setValue(45.0)
        self.spin_ymin = QDoubleSpinBox(); self.spin_ymin.setValue(15.0)
        self.spin_ymax = QDoubleSpinBox(); self.spin_ymax.setValue(40.0)
        self.spin_rmin = QDoubleSpinBox(); self.spin_rmin.setValue(10.0)
        self.spin_rmax = QDoubleSpinBox(); self.spin_rmax.setValue(45.0)

        h_x = QHBoxLayout(); h_x.addWidget(self.spin_xmin); h_x.addWidget(QLabel("~")); h_x.addWidget(self.spin_xmax)
        h_y = QHBoxLayout(); h_y.addWidget(self.spin_ymin); h_y.addWidget(QLabel("~")); h_y.addWidget(self.spin_ymax)
        h_r = QHBoxLayout(); h_r.addWidget(self.spin_rmin); h_r.addWidget(QLabel("~")); h_r.addWidget(self.spin_rmax)

        form_algo.addRow("Xc 包络 (m):", h_x)
        form_algo.addRow("Yc 包络 (m):", h_y)
        form_algo.addRow("半径 R 包络 (m):", h_r)
        grp_algo.setLayout(form_algo)
        layout.addWidget(grp_algo)

        h_btn_search = QHBoxLayout()
        self.btn_search = QPushButton("启动最危险滑面搜索")
        self.btn_search.setIcon(get_icon("search_surface"))
        self.btn_search.setStyleSheet("background-color: #d35400; color: white; font-weight: bold; padding: 6px;")
        self.btn_search.clicked.connect(self.search_requested.emit)

        self.btn_stop = QPushButton("终止搜索")
        self.btn_stop.setIcon(get_icon("stop_search"))
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.search_stop_requested.emit)

        h_btn_search.addWidget(self.btn_search)
        h_btn_search.addWidget(self.btn_stop)
        layout.addLayout(h_btn_search)

        self.prog_bar = QProgressBar()
        self.prog_bar.setValue(0)
        layout.addWidget(self.prog_bar)

        self.lbl_best = QLabel("最危险滑弧: 未搜索")
        self.lbl_best.setStyleSheet("font-weight: bold; color: #c0392b;")
        layout.addWidget(self.lbl_best)

        btn_apply = QPushButton("应用最危险滑面至模型")
        btn_apply.setIcon(get_icon("apply_surface"))
        btn_apply.clicked.connect(self.apply_searched_circle.emit)
        layout.addWidget(btn_apply)

        btn_run_all = QPushButton("运行全部 5 种 LEM 模型求解")
        btn_run_all.setIcon(get_icon("run_solvers"))
        btn_run_all.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; font-size: 13px; padding: 8px;")
        btn_run_all.clicked.connect(self.calculate_requested.emit)
        layout.addWidget(btn_run_all)

        layout.addStretch()
        self.setWidget(container)

    def get_circle_params(self) -> Tuple[float, float, float, int]:
        return (self.spin_xc.value(), self.spin_yc.value(), self.spin_r.value(), self.spin_slices.value())

    def set_circle_params(self, xc: float, yc: float, R: float):
        self.spin_xc.setValue(xc)
        self.spin_yc.setValue(yc)
        self.spin_r.setValue(R)

    def get_search_config(self):
        algo_name = self.combo_algo.currentText()
        eval_name = "Bishop" if "Bishop" in self.combo_eval.currentText() else "Fellenius"
        bounds = [
            (self.spin_xmin.value(), self.spin_xmax.value()),
            (self.spin_ymin.value(), self.spin_ymax.value()),
            (self.spin_rmin.value(), self.spin_rmax.value()),
        ]
        return algo_name, eval_name, bounds


class ResultsDockWidget(QDockWidget):
    """计算结果、降雨时程与微元表格停靠窗"""
    def __init__(self, parent=None):
        super().__init__("计算成果与切片受力核查", parent)
        self.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)
        self._init_ui()

    def _init_ui(self):
        self.tabs = QTabWidget()

        self.tbl_summary = QTableWidget(5, 3)
        self.tbl_summary.setHorizontalHeaderLabels(["极限平衡求解方法", "稳定安全系数 (Fs)", "平衡条件与收敛状态"])
        self.tbl_summary.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabs.addTab(self.tbl_summary, "经典 LEM 模型对比表")

        self.tbl_time_series = QTableWidget(0, 4)
        self.tbl_time_series.setHorizontalHeaderLabels(["降雨历时 t (h)", "降雨强度 (mm/h)", "湿润锋深度 zf (m)", "安全系数 Fs (Bishop)"])
        self.tbl_time_series.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabs.addTab(self.tbl_time_series, "降雨历时稳定性衰减 Fs(t)")

        self.tbl_slices = QTableWidget(0, 15)
        self.tbl_slices.setHorizontalHeaderLabels([
            "条号", "所属土层", "中点X(m)", "条宽b(m)", "高度h(m)",
            "土自重(kN)", "外载荷(kN)", "总竖力W(kN)", "地震力Fh(kN)",
            "孔压u(kPa)", "基质吸力(kPa)", "总黏聚力(kPa)", "摩擦角(°)", "底坡角α(°)", "底斜长l(m)"
        ])
        self.tbl_slices.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tabs.addTab(self.tbl_slices, "离散土条微元多物理量明细")

        self.setWidget(self.tabs)

    def display_summary(self, results: List[Tuple[str, Tuple[Optional[float], str]]]):
        self.tbl_summary.setRowCount(len(results))
        for r, (name, (fs, note)) in enumerate(results):
            self.tbl_summary.setItem(r, 0, QTableWidgetItem(name))
            fs_text = f"{fs:.4f}" if fs is not None else "未收敛"
            item_fs = QTableWidgetItem(fs_text)
            item_fs.setTextAlignment(Qt.AlignCenter)
            self.tbl_summary.setItem(r, 1, item_fs)
            self.tbl_summary.setItem(r, 2, QTableWidgetItem(note))

    def display_time_series(self, time_results: List[Tuple[float, float, float, float]]):
        self.tbl_time_series.setRowCount(len(time_results))
        for r, (t, intensity, depth, fs) in enumerate(time_results):
            self.tbl_time_series.setItem(r, 0, QTableWidgetItem(f"{t:.1f}"))
            self.tbl_time_series.setItem(r, 1, QTableWidgetItem(f"{intensity:.1f}"))
            self.tbl_time_series.setItem(r, 2, QTableWidgetItem(f"{depth:.2f}"))
            item_fs = QTableWidgetItem(f"{fs:.4f}" if fs > 0 else "未收敛")
            item_fs.setTextAlignment(Qt.AlignCenter)
            self.tbl_time_series.setItem(r, 3, item_fs)
        self.tabs.setCurrentWidget(self.tbl_time_series)

    def display_slices(self, slices: Optional[List[Slice]]):
        if not slices:
            self.tbl_slices.setRowCount(0)
            return

        self.tbl_slices.setRowCount(len(slices))
        for r, s in enumerate(slices):
            self.tbl_slices.setItem(r, 0, QTableWidgetItem(str(s.index)))
            self.tbl_slices.setItem(r, 1, QTableWidgetItem(str(s.layer_name)))
            self.tbl_slices.setItem(r, 2, QTableWidgetItem(f"{s.xm:.2f}"))
            self.tbl_slices.setItem(r, 3, QTableWidgetItem(f"{s.b:.2f}"))
            self.tbl_slices.setItem(r, 4, QTableWidgetItem(f"{s.h:.2f}"))
            self.tbl_slices.setItem(r, 5, QTableWidgetItem(f"{s.W_soil:.2f}"))
            self.tbl_slices.setItem(r, 6, QTableWidgetItem(f"{s.q_load:.2f}"))
            self.tbl_slices.setItem(r, 7, QTableWidgetItem(f"{s.W:.2f}"))
            self.tbl_slices.setItem(r, 8, QTableWidgetItem(f"{s.Fh:.2f}"))
            self.tbl_slices.setItem(r, 9, QTableWidgetItem(f"{s.u:.2f}"))
            self.tbl_slices.setItem(r, 10, QTableWidgetItem(f"{s.suction:.2f}"))
            self.tbl_slices.setItem(r, 11, QTableWidgetItem(f"{s.c:.2f}"))
            self.tbl_slices.setItem(r, 12, QTableWidgetItem(f"{np.degrees(s.phi):.1f}"))
            self.tbl_slices.setItem(r, 13, QTableWidgetItem(f"{np.degrees(s.alpha):.2f}"))
            self.tbl_slices.setItem(r, 14, QTableWidgetItem(f"{s.l:.2f}"))