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
    QProgressBar, QCheckBox, QTreeWidget, QTreeWidgetItem, QSlider, QScrollArea, QFrame, QRadioButton, QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from core.slip_surface import BaseSlipSurface, CircularSlipSurface, PolygonalSlipSurface
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
    
    def to_dict(self) -> Dict[str, Any]:
        self._save_current_table_data()
        return {
            "ground": [list(p) for p in self.data_ground],
            "water":  [list(p) for p in self.data_water] if self.data_water else None,
            "strata": [[list(p) for p in line] for line in self.data_strata],
        }

    def from_dict(self, data: Dict[str, Any]):
        if not isinstance(data, dict):
            return
        if data.get("ground") and len(data["ground"]) >= 2:
            self.data_ground = [(float(x), float(y)) for x, y in data["ground"]]
        if data.get("water"):
            self.data_water = [(float(x), float(y)) for x, y in data["water"]]
        else:
            self.data_water = None

        self.data_strata = []
        for line in data.get("strata", []) or []:
            if len(line) >= 2:
                self.data_strata.append([(float(x), float(y)) for x, y in line])

        # 重建地层树
        while self.item_strata_root.childCount() > 0:
            self.item_strata_root.removeChild(self.item_strata_root.child(0))
        for idx, line in enumerate(self.data_strata):
            child = QTreeWidgetItem([f"第{idx + 1}分界面", str(len(line))])
            self.item_strata_root.addChild(child)
        self.item_strata_root.setText(1, str(len(self.data_strata)))

        # 刷新当前正在编辑的表
        self.tree.setCurrentItem(self.item_ground)
        self._load_table_data(self.data_ground)


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
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_regime": self.combo_regime.currentIndex(),
            "current_layer": self.combo_layer.currentIndex(),
            "layers": [
                {
                    "name": m.name,
                    "gamma_dry": m.gamma_dry,
                    "gamma_sat": m.gamma_sat,
                    "c_prime": m.c_prime,
                    "phi_deg": m.phi_deg,
                    "is_unsaturated": m.is_unsaturated,
                    "phi_b_deg": m.phi_b_deg,
                    "suction_cutoff": m.suction_cutoff,
                }
                for m in self.materials_db
            ],
        }

    def from_dict(self, data: Dict[str, Any]):
        if not isinstance(data, dict):
            return
        layers = data.get("layers", [])
        if layers:
            new_db = []
            for L in layers:
                new_db.append(SoilMaterial(
                    name=L.get("name", "土层"),
                    gamma_dry=float(L.get("gamma_dry", 19.0)),
                    gamma_sat=float(L.get("gamma_sat", 21.0)),
                    c_prime=float(L.get("c_prime", 15.0)),
                    phi_deg=float(L.get("phi_deg", 20.0)),
                    is_unsaturated=bool(L.get("is_unsaturated", False)),
                    phi_b_deg=float(L.get("phi_b_deg", 15.0)),
                    suction_cutoff=float(L.get("suction_cutoff", 100.0)),
                ))
            self.materials_db = new_db

        # 恢复 combo 选择
        regime = int(data.get("active_regime", 0))
        self.combo_regime.setCurrentIndex(regime)
        self.grp_unsat.setEnabled(regime == 1)

        layer_idx = int(data.get("current_layer", 0))
        if 0 <= layer_idx < len(self.materials_db):
            self.combo_layer.setCurrentIndex(layer_idx)
            self._load_layer_params(layer_idx)

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
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "series": [[float(t), float(i)] for t, i in self._get_time_series_data()],
            "ks_mm_h": self.spin_ks.value(),
            "delta_theta": self.spin_theta.value(),
            "current_time": self.slider_time.value(),
        }

    def from_dict(self, data: Dict[str, Any]):
        if not isinstance(data, dict):
            return
        series = data.get("series", [])
        if series:
            self.tbl_rain.setRowCount(len(series))
            for r, (t, i) in enumerate(series):
                self.tbl_rain.setItem(r, 0, QTableWidgetItem(str(t)))
                self.tbl_rain.setItem(r, 1, QTableWidgetItem(str(i)))

        self.spin_ks.setValue(float(data.get("ks_mm_h", 15.0)))
        self.spin_theta.setValue(float(data.get("delta_theta", 0.20)))
        self.slider_time.setValue(int(data.get("current_time", 0)))

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
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "q": self.spin_q.value(),
            "x1": self.spin_qx1.value(),
            "x2": self.spin_qx2.value(),
            "kh": self.spin_kh.value(),
        }

    def from_dict(self, data: Dict[str, Any]):
        if not isinstance(data, dict):
            return
        self.spin_q.setValue(float(data.get("q", 0.0)))
        self.spin_qx1.setValue(float(data.get("x1", 5.0)))
        self.spin_qx2.setValue(float(data.get("x2", 18.0)))
        self.spin_kh.setValue(float(data.get("kh", 0.0)))


class SearchDockWidget(QDockWidget):
    """支持圆弧与非圆弧折线双模式定义与全局寻优控制面板

    非圆弧模式支持两种行为:
      - 自动搜索 (chk_poly_auto_search 勾选): 表格里的点作为形状参考, DE 搜索最优
      - 手动试算 (chk_poly_auto_search 未勾选): 表格里的点就是最终滑面, 只算一次 Fs
    """
    calculate_requested = pyqtSignal()
    search_requested = pyqtSignal()
    search_stop_requested = pyqtSignal()
    apply_searched_circle = pyqtSignal()
    preview_circle_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("滑面定义与全局稳定性寻优", parent)
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self._init_ui()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _init_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)

        # ---------- 1. 滑动面形态选择 ----------
        grp_shape = QGroupBox("1. 滑动面形态选择 (Slip Surface Shape)")
        f_shape = QFormLayout()
        self.combo_surface_type = QComboBox()
        self.combo_surface_type.addItems([
            "圆弧滑动面 (Circular)",
            "非圆弧多段折线面 (Polygonal / Non-Circular)"
        ])
        self.combo_surface_type.currentIndexChanged.connect(self._on_surface_type_changed)
        f_shape.addRow("滑面类型:", self.combo_surface_type)
        grp_shape.setLayout(f_shape)
        layout.addWidget(grp_shape)

        # ---------- 2. 圆弧几何参数 ----------
        self.grp_circle = QGroupBox("圆弧几何参数 (指定滑面)")
        form_circle = QFormLayout()
        self.spin_xc = QDoubleSpinBox(); self.spin_xc.setRange(-200.0, 500.0); self.spin_xc.setValue(25.0); self.spin_xc.setSuffix(" m")
        self.spin_yc = QDoubleSpinBox(); self.spin_yc.setRange(-200.0, 500.0); self.spin_yc.setValue(22.0); self.spin_yc.setSuffix(" m")
        self.spin_r = QDoubleSpinBox(); self.spin_r.setRange(1.0, 500.0); self.spin_r.setValue(23.0); self.spin_r.setSuffix(" m")
        self.spin_slices = QSpinBox(); self.spin_slices.setRange(10, 150); self.spin_slices.setValue(30); self.spin_slices.setSuffix(" 个")
        form_circle.addRow("滑弧圆心 Xc:", self.spin_xc)
        form_circle.addRow("滑弧圆心 Yc:", self.spin_yc)
        form_circle.addRow("滑弧半径 R:", self.spin_r)
        form_circle.addRow("切片土条数 N:", self.spin_slices)
        self.grp_circle.setLayout(form_circle)
        layout.addWidget(self.grp_circle)

        # ---------- 3. 非圆弧控制折点表 ----------
        self.grp_poly = QGroupBox("非圆弧控制折点表 (指定滑面)")
        l_poly = QVBoxLayout()

        # 3.1 双模式复选框
        self.chk_poly_auto_search = QCheckBox("启用自动搜索 (未勾选则仅按表中坐标试算)")
        self.chk_poly_auto_search.setChecked(True)
        self.chk_poly_auto_search.setToolTip(
            "✓ 勾选: 表格里的点作为形状参考, 算法在附近搜索最优滑面\n"
            "✗ 未勾选: 表格里的点就是最终滑面, 只算一次 Fs"
        )
        l_poly.addWidget(self.chk_poly_auto_search)

        # 3.2 折点表
        self.tbl_poly = QTableWidget(3, 2)
        self.tbl_poly.setHorizontalHeaderLabels(["X 坐标 (m)", "Y 高程 (m)"])
        default_poly = [(12.0, 15.0), (25.0, 4.0), (38.0, 0.0)]
        for r, (x, y) in enumerate(default_poly):
            self.tbl_poly.setItem(r, 0, QTableWidgetItem(str(x)))
            self.tbl_poly.setItem(r, 1, QTableWidgetItem(str(y)))
        self.tbl_poly.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_poly.itemChanged.connect(lambda _: self.preview_circle_changed.emit())
        l_poly.addWidget(self.tbl_poly)

        # 3.3 增删点按钮
        btn_poly_bar = QHBoxLayout()
        btn_add_p = QPushButton("添加折点")
        btn_add_p.clicked.connect(self._add_poly_point)
        btn_del_p = QPushButton("删除选中")
        btn_del_p.clicked.connect(self._del_poly_point)
        btn_poly_bar.addWidget(btn_add_p)
        btn_poly_bar.addWidget(btn_del_p)
        l_poly.addLayout(btn_poly_bar)

        self.grp_poly.setLayout(l_poly)
        self.grp_poly.setVisible(False)
        layout.addWidget(self.grp_poly)

        # ---------- 4. 预览按钮 ----------
        btn_preview = QPushButton("刷新并预览当前滑面网格")
        btn_preview.setIcon(get_icon("refresh"))
        btn_preview.clicked.connect(self.preview_circle_changed.emit)
        layout.addWidget(btn_preview)

        # ---------- 5. 选用力学模型 ----------
        grp_solver = QGroupBox("2. 选用求解模型 (Target Method)")
        f_solver = QFormLayout()
        self.combo_solver = QComboBox()
        self.combo_solver.addItems([
            "斯宾塞法 (Spencer 完全平衡法) [通用]",
            "摩根斯坦-普赖斯法 (Morgenstern-Price) [通用]",
            "简化让布法 (Simplified Janbu) [通用]",
            "简化毕肖普法 (Simplified Bishop) [仅圆弧]",
            "瑞典条分法 (Fellenius / Ordinary) [仅圆弧]"
        ])
        f_solver.addRow("力学模型:", self.combo_solver)
        grp_solver.setLayout(f_solver)
        layout.addWidget(grp_solver)

        # ---------- 6. 全局寻优设置 ----------
        self.grp_algo = QGroupBox("3. 最危险滑面全局寻优")
        self.form_algo = QFormLayout()
        self.combo_algo = QComboBox()
        self.combo_algo.addItems([
            "差分进化算法 (Differential Evolution, 推荐)",
            "粒子群优化算法 (PSO)",
            "模拟退火算法 (Simulated Annealing)",
            "单纯形搜索法 (Nelder-Mead)",
            "传统网格扫描法 (Grid Search)"
        ])
        self.combo_eval = QComboBox()
        self.combo_eval.addItems([
            "Spencer 完全平衡法",
            "Simplified Bishop (圆弧)",
            "Simplified Janbu"
        ])
        self.form_algo.addRow("寻优算法:", self.combo_algo)
        self.form_algo.addRow("寻优评价模型:", self.combo_eval)

        # 范围包络控件 (自适应圆弧/折线标签)
        self.lbl_b1 = QLabel("Xc 搜索范围 (m):")
        self.lbl_b2 = QLabel("Yc 搜索范围 (m):")
        self.lbl_b3 = QLabel("半径 R 范围 (m):")
        self.spin_b1_min = QDoubleSpinBox(); self.spin_b1_min.setRange(-500, 500); self.spin_b1_min.setValue(10.0)
        self.spin_b1_max = QDoubleSpinBox(); self.spin_b1_max.setRange(-500, 500); self.spin_b1_max.setValue(45.0)
        self.spin_b2_min = QDoubleSpinBox(); self.spin_b2_min.setRange(-500, 500); self.spin_b2_min.setValue(15.0)
        self.spin_b2_max = QDoubleSpinBox(); self.spin_b2_max.setRange(-500, 500); self.spin_b2_max.setValue(40.0)
        self.spin_b3_min = QDoubleSpinBox(); self.spin_b3_min.setRange(-500, 500); self.spin_b3_min.setValue(10.0)
        self.spin_b3_max = QDoubleSpinBox(); self.spin_b3_max.setRange(-500, 500); self.spin_b3_max.setValue(45.0)

        h_b1 = QHBoxLayout(); h_b1.addWidget(self.spin_b1_min); h_b1.addWidget(QLabel("~")); h_b1.addWidget(self.spin_b1_max)
        h_b2 = QHBoxLayout(); h_b2.addWidget(self.spin_b2_min); h_b2.addWidget(QLabel("~")); h_b2.addWidget(self.spin_b2_max)
        h_b3 = QHBoxLayout(); h_b3.addWidget(self.spin_b3_min); h_b3.addWidget(QLabel("~")); h_b3.addWidget(self.spin_b3_max)

        self.form_algo.addRow(self.lbl_b1, h_b1)
        self.form_algo.addRow(self.lbl_b2, h_b2)
        self.form_algo.addRow(self.lbl_b3, h_b3)
        self.grp_algo.setLayout(self.form_algo)
        layout.addWidget(self.grp_algo)

        # ---------- 7. 控制按钮 + 进度条 + 结果 ----------
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

        self.lbl_best = QLabel("最危险滑面: 未搜索")
        self.lbl_best.setStyleSheet("font-weight: bold; color: #c0392b; font-size: 13px;")
        layout.addWidget(self.lbl_best)

        self.btn_apply = QPushButton("应用最危险滑面至模型")
        self.btn_apply.setIcon(get_icon("apply_surface"))
        self.btn_apply.clicked.connect(self.apply_searched_circle.emit)
        layout.addWidget(self.btn_apply)

        # ---------- 8. 定向执行分析主按钮 ----------
        self.btn_run_all = QPushButton("执行稳定性分析 (所选模型)")
        self.btn_run_all.setIcon(get_icon("run_solvers"))
        self.btn_run_all.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; font-size: 13px; padding: 8px;")
        self.btn_run_all.clicked.connect(self.calculate_requested.emit)
        layout.addWidget(self.btn_run_all)

        layout.addStretch()

        # ---------- 9. 滚动容器 ----------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(container)
        self.setWidget(scroll)

    # ------------------------------------------------------------------
    # 滑面类型切换
    # ------------------------------------------------------------------
    def _on_surface_type_changed(self, idx: int):
        is_circle = (idx == 0)

        # 1. 切换指定滑面参数面板
        if hasattr(self, "grp_circle"):
            self.grp_circle.setVisible(is_circle)
        if hasattr(self, "grp_poly"):
            self.grp_poly.setVisible(not is_circle)

        # 2. 寻优面板始终启用，仅动态更新标题
        if hasattr(self, "grp_algo"):
            self.grp_algo.setEnabled(True)
            if is_circle:
                self.grp_algo.setTitle("3. 最危险滑面全局寻优 (圆弧: Xc, Yc, R 搜索范围)")
            else:
                self.grp_algo.setTitle("3. 最危险滑面全局寻优 (非圆弧: 端点X, 底标高Y 搜索范围)")

        # 3. 求解模型适用性过滤
        if hasattr(self, "combo_solver"):
            for i in range(self.combo_solver.count()):
                txt = self.combo_solver.itemText(i)
                if "仅圆弧" in txt:
                    self.combo_solver.model().item(i).setEnabled(is_circle)
            if not is_circle and "仅圆弧" in self.combo_solver.currentText():
                self.combo_solver.setCurrentIndex(0)

        # 4. 双模式复选框仅对非圆弧可用
        if hasattr(self, "chk_poly_auto_search"):
            self.chk_poly_auto_search.setEnabled(not is_circle)

        # 5. 更新 bounds 标签
        if hasattr(self, "lbl_b1"):
            if is_circle:
                self.lbl_b1.setText("Xc 搜索范围 (m):")
                self.lbl_b2.setText("Yc 搜索范围 (m):")
                self.lbl_b3.setText("半径 R 范围 (m):")
            else:
                self.lbl_b1.setText("后缘 X 范围 (m):")
                self.lbl_b2.setText("滑底 Y 范围 (m):")
                self.lbl_b3.setText("坡脚 X 范围 (m):")

        # 6. 触发剖分与渲染
        self.preview_circle_changed.emit()

    # ------------------------------------------------------------------
    # 折点表操作
    # ------------------------------------------------------------------
    def _add_poly_point(self):
        row = self.tbl_poly.rowCount()
        self.tbl_poly.insertRow(row)
        self.tbl_poly.setItem(row, 0, QTableWidgetItem("30.0"))
        self.tbl_poly.setItem(row, 1, QTableWidgetItem("2.0"))
        self.preview_circle_changed.emit()

    def _del_poly_point(self):
        cur = self.tbl_poly.currentRow()
        if cur >= 0 and self.tbl_poly.rowCount() > 2:
            self.tbl_poly.removeRow(cur)
            self.preview_circle_changed.emit()

    def get_poly_points(self):
        """从折点表读取所有有效点 (按 X 升序)"""
        pts = []
        for r in range(self.tbl_poly.rowCount()):
            try:
                x_item = self.tbl_poly.item(r, 0)
                y_item = self.tbl_poly.item(r, 1)
                if x_item is None or y_item is None:
                    continue
                x = float(x_item.text())
                y = float(y_item.text())
                pts.append((x, y))
            except (ValueError, AttributeError):
                continue
        pts.sort(key=lambda p: p[0])
        return pts

    def set_poly_points(self, points):
        """把 [(x,y), ...] 回填到折点表"""
        self.tbl_poly.blockSignals(True)
        self.tbl_poly.setRowCount(len(points))
        for r, (x, y) in enumerate(points):
            self.tbl_poly.setItem(r, 0, QTableWidgetItem(f"{float(x):.3f}"))
            self.tbl_poly.setItem(r, 1, QTableWidgetItem(f"{float(y):.3f}"))
        self.tbl_poly.blockSignals(False)
        self.preview_circle_changed.emit()

    # ------------------------------------------------------------------
    # 双模式开关
    # ------------------------------------------------------------------
    def get_poly_auto_search(self) -> bool:
        return bool(self.chk_poly_auto_search.isChecked())

    def set_poly_auto_search(self, flag: bool):
        self.chk_poly_auto_search.setChecked(bool(flag))

    # ------------------------------------------------------------------
    # 供 MainWindow 调用的接口
    # ------------------------------------------------------------------
    def get_surface_type(self) -> str:
        return "circular" if self.combo_surface_type.currentIndex() == 0 else "polygonal"

    def get_circle_params(self):
        return (self.spin_xc.value(), self.spin_yc.value(),
                self.spin_r.value(), self.spin_slices.value())

    def set_circle_params(self, xc: float, yc: float, R: float):
        self.spin_xc.setValue(xc)
        self.spin_yc.setValue(yc)
        self.spin_r.setValue(R)

    def get_slip_surface(self):
        """获取当前界面的滑面对象"""
        from core.slip_surface import CircularSlipSurface, PolygonalSlipSurface
        if self.combo_surface_type.currentIndex() == 0:
            return CircularSlipSurface(
                self.spin_xc.value(), self.spin_yc.value(), self.spin_r.value()
            )
        else:
            pts = self.get_poly_points()
            if len(pts) < 2:
                pts = [(12.0, 15.0), (25.0, 4.0), (38.0, 0.0)]
            return PolygonalSlipSurface(pts)

    def get_selected_method_name(self) -> str:
        return self.combo_solver.currentText()

    def get_search_config(self):
        stype = self.get_surface_type()
        algo_name = self.combo_algo.currentText()

        txt = self.combo_eval.currentText()
        if "Janbu" in txt:
            eval_name = "Janbu"
        elif "Bishop" in txt:
            eval_name = "Bishop"
        elif "Spencer" in txt:
            eval_name = "Spencer"
        else:
            eval_name = "Spencer"

        bounds = [
            (self.spin_b1_min.value(), self.spin_b1_max.value()),
            (self.spin_b2_min.value(), self.spin_b2_max.value()),
            (self.spin_b3_min.value(), self.spin_b3_max.value()),
        ]
        ref_pts = self.get_poly_points()
        auto_search = self.get_poly_auto_search()
        return stype, algo_name, eval_name, bounds, ref_pts, auto_search

    # ------------------------------------------------------------------
    # 工程文件持久化
    # ------------------------------------------------------------------
    def to_dict(self):
        return {
            "surface_type": self.get_surface_type(),
            "circle": {
                "xc": self.spin_xc.value(),
                "yc": self.spin_yc.value(),
                "R":  self.spin_r.value(),
                "n_slices": self.spin_slices.value(),
            },
            "polygon": [list(p) for p in self.get_poly_points()],
            "poly_auto_search": self.get_poly_auto_search(),
            "search_bounds": {
                "b1": [self.spin_b1_min.value(), self.spin_b1_max.value()],
                "b2": [self.spin_b2_min.value(), self.spin_b2_max.value()],
                "b3": [self.spin_b3_min.value(), self.spin_b3_max.value()],
            },
            "search_algo": self.combo_algo.currentIndex(),
            "search_eval": self.combo_eval.currentIndex(),
            "solver_method": self.combo_solver.currentIndex(),
        }

    def from_dict(self, data):
        if not isinstance(data, dict):
            return

        # 滑面类型
        stype = data.get("surface_type", "circular")
        self.combo_surface_type.setCurrentIndex(0 if stype == "circular" else 1)

        # 圆弧参数
        c = data.get("circle", {}) or {}
        self.spin_xc.setValue(float(c.get("xc", 25.0)))
        self.spin_yc.setValue(float(c.get("yc", 22.0)))
        self.spin_r.setValue(float(c.get("R", 23.0)))
        self.spin_slices.setValue(int(c.get("n_slices", 30)))

        # 折线点
        poly = data.get("polygon", [])
        if poly:
            self.tbl_poly.blockSignals(True)
            self.tbl_poly.setRowCount(len(poly))
            for r, (x, y) in enumerate(poly):
                self.tbl_poly.setItem(r, 0, QTableWidgetItem(f"{float(x):.3f}"))
                self.tbl_poly.setItem(r, 1, QTableWidgetItem(f"{float(y):.3f}"))
            self.tbl_poly.blockSignals(False)

        # 双模式
        if "poly_auto_search" in data:
            self.set_poly_auto_search(bool(data["poly_auto_search"]))

        # 搜索包络
        b = data.get("search_bounds", {}) or {}
        for key, spin_min, spin_max in (
            ("b1", self.spin_b1_min, self.spin_b1_max),
            ("b2", self.spin_b2_min, self.spin_b2_max),
            ("b3", self.spin_b3_min, self.spin_b3_max),
        ):
            pair = b.get(key)
            if pair and len(pair) == 2:
                spin_min.setValue(float(pair[0]))
                spin_max.setValue(float(pair[1]))

        # 算法与模型
        if "search_algo" in data:
            self.combo_algo.setCurrentIndex(int(data["search_algo"]))
        if "search_eval" in data:
            self.combo_eval.setCurrentIndex(int(data["search_eval"]))
        if "solver_method" in data:
            self.combo_solver.setCurrentIndex(int(data["solver_method"]))

        # 让界面根据类型刷新
        self._on_surface_type_changed(self.combo_surface_type.currentIndex())
        
        
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
            
    def get_poly_points(self):
        """从折线表格读回所有点 (供保存使用)"""
        pts = []
        for r in range(self.tbl_poly.rowCount()):
            try:
                x = float(self.tbl_poly.item(r, 0).text())
                y = float(self.tbl_poly.item(r, 1).text())
                pts.append((x, y))
            except Exception:
                continue
        return pts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "surface_type": self.get_surface_type(),
            "circle": {
                "xc": self.spin_xc.value(),
                "yc": self.spin_yc.value(),
                "R": self.spin_r.value(),
                "n_slices": self.spin_slices.value(),
            },
            "polygon": [list(p) for p in self.get_poly_points()],
            "search_bounds": {
                "b1": [self.spin_b1_min.value(), self.spin_b1_max.value()],
                "b2": [self.spin_b2_min.value(), self.spin_b2_max.value()],
                "b3": [self.spin_b3_min.value(), self.spin_b3_max.value()],
            },
            "search_algo": self.combo_algo.currentIndex(),
            "search_eval": self.combo_eval.currentIndex(),
            "solver_method": self.combo_solver.currentIndex(),
        }

    def from_dict(self, data: Dict[str, Any]):
        if not isinstance(data, dict):
            return

        # 滑面类型
        stype = data.get("surface_type", "circular")
        self.combo_surface_type.setCurrentIndex(0 if stype == "circular" else 1)

        # 圆弧参数
        c = data.get("circle", {}) or {}
        self.spin_xc.setValue(float(c.get("xc", 25.0)))
        self.spin_yc.setValue(float(c.get("yc", 22.0)))
        self.spin_r.setValue(float(c.get("R", 23.0)))
        self.spin_slices.setValue(int(c.get("n_slices", 30)))

        # 折线点
        poly = data.get("polygon", [])
        if poly:
            self.tbl_poly.blockSignals(True)
            self.tbl_poly.setRowCount(len(poly))
            for r, (x, y) in enumerate(poly):
                self.tbl_poly.setItem(r, 0, QTableWidgetItem(f"{float(x):.3f}"))
                self.tbl_poly.setItem(r, 1, QTableWidgetItem(f"{float(y):.3f}"))
            self.tbl_poly.blockSignals(False)

        # 搜索包络
        b = data.get("search_bounds", {}) or {}
        for key, spin_min, spin_max in (
            ("b1", self.spin_b1_min, self.spin_b1_max),
            ("b2", self.spin_b2_min, self.spin_b2_max),
            ("b3", self.spin_b3_min, self.spin_b3_max),
        ):
            pair = b.get(key, None)
            if pair and len(pair) == 2:
                spin_min.setValue(float(pair[0]))
                spin_max.setValue(float(pair[1]))

        # 算法与模型选择
        if "search_algo" in data:
            self.combo_algo.setCurrentIndex(int(data["search_algo"]))
        if "search_eval" in data:
            self.combo_eval.setCurrentIndex(int(data["search_eval"]))
        if "solver_method" in data:
            self.combo_solver.setCurrentIndex(int(data["solver_method"]))

        # 让界面根据类型刷新一次
        self._on_surface_type_changed(self.combo_surface_type.currentIndex())

    
class ReliabilityDockWidget(QDockWidget):
    """边坡可靠度指标与失效概率评价停靠窗 (CAD/CAE 风格)"""
    reliability_requested = pyqtSignal()
    reliability_stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("边坡可靠度与失效概率评价", parent)
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
        self._init_ui()

    def _init_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)

        # 1. 评价算法与抽样规模设置
        grp_method = QGroupBox("可靠度评价算法与抽样规模")
        f_method = QFormLayout()

        self.combo_rel_method = QComboBox()
        self.combo_rel_method.addItems([
            "蒙特卡洛模拟法 (MCS, 随机抽样)",
            "Rosenblueth 点估计法 (PEM, 快速核算)"
        ])

        self.combo_eval_method = QComboBox()
        self.combo_eval_method.addItems(["Simplified Bishop (推荐)", "Fellenius / Ordinary"])

        self.spin_n_sim = QSpinBox()
        self.spin_n_sim.setRange(100, 200000)
        self.spin_n_sim.setValue(5000)
        self.spin_n_sim.setSingleStep(1000)
        self.spin_n_sim.setSuffix(" 次")

        f_method.addRow("可靠度算法:", self.combo_rel_method)
        f_method.addRow("基础条分模型:", self.combo_eval_method)
        f_method.addRow("MCS 抽样次数:", self.spin_n_sim)
        grp_method.setLayout(f_method)
        layout.addWidget(grp_method)

        # 2. 岩土力学参数概率统计特征
        grp_stats = QGroupBox("岩土力学参数概率统计特征")
        f_stats = QFormLayout()

        self.spin_cov_c = QDoubleSpinBox()
        self.spin_cov_c.setRange(0.01, 1.0)
        self.spin_cov_c.setValue(0.25)
        self.spin_cov_c.setSingleStep(0.05)

        self.combo_dist_c = QComboBox()
        self.combo_dist_c.addItems(["对数正态分布", "正态分布"])

        self.spin_cov_phi = QDoubleSpinBox()
        self.spin_cov_phi.setRange(0.01, 1.0)
        self.spin_cov_phi.setValue(0.15)
        self.spin_cov_phi.setSingleStep(0.05)

        self.combo_dist_phi = QComboBox()
        self.combo_dist_phi.addItems(["对数正态分布", "正态分布"])

        self.spin_rho = QDoubleSpinBox()
        self.spin_rho.setRange(-0.95, 0.95)
        self.spin_rho.setValue(-0.50)
        self.spin_rho.setSingleStep(0.05)

        self.spin_cov_gamma = QDoubleSpinBox()
        self.spin_cov_gamma.setRange(0.01, 0.5)
        self.spin_cov_gamma.setValue(0.08)
        self.spin_cov_gamma.setSingleStep(0.02)

        f_stats.addRow("黏聚力 c' 变异系数 (COV):", self.spin_cov_c)
        f_stats.addRow("黏聚力 c' 概率分布:", self.combo_dist_c)
        f_stats.addRow("摩擦角 φ' 变异系数 (COV):", self.spin_cov_phi)
        f_stats.addRow("摩擦角 φ' 概率分布:", self.combo_dist_phi)
        f_stats.addRow("c'-φ' 互相关系数 (ρ):", self.spin_rho)
        f_stats.addRow("天然重度 γ 变异系数 (COV):", self.spin_cov_gamma)
        grp_stats.setLayout(f_stats)
        layout.addWidget(grp_stats)

        # 3. 运行控制与实时进度条
        h_btn = QHBoxLayout()
        self.btn_run_rel = QPushButton("启动失效概率评价")
        ico_run = get_icon("run_solvers")
        if ico_run:
            self.btn_run_rel.setIcon(ico_run)
        self.btn_run_rel.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; padding: 6px;")
        self.btn_run_rel.clicked.connect(self.reliability_requested.emit)

        self.btn_stop_rel = QPushButton("终止评价")
        ico_stop = get_icon("stop_search")
        if ico_stop:
            self.btn_stop_rel.setIcon(ico_stop)
        self.btn_stop_rel.setEnabled(False)
        self.btn_stop_rel.setStyleSheet("padding: 6px;")
        self.btn_stop_rel.clicked.connect(self.reliability_stop_requested.emit)

        h_btn.addWidget(self.btn_run_rel)
        h_btn.addWidget(self.btn_stop_rel)
        layout.addLayout(h_btn)

        self.prog_bar = QProgressBar()
        self.prog_bar.setValue(0)
        layout.addWidget(self.prog_bar)

        # 4. 评价成果数据展示卡片
        grp_res = QGroupBox("边坡可靠度与风险成果指标")
        f_res = QFormLayout()

        self.lbl_pf = QLabel("未分析")
        self.lbl_pf.setStyleSheet("font-size: 15px; font-weight: bold; color: #c0392b;")
        self.lbl_beta = QLabel("未分析")
        self.lbl_beta.setStyleSheet("font-size: 15px; font-weight: bold; color: #2980b9;")
        self.lbl_fs_mean_std = QLabel("未分析")
        self.lbl_fs_range = QLabel("未分析")
        self.lbl_fail_counts = QLabel("未分析")

        f_res.addRow("失稳破坏概率 (Pf):", self.lbl_pf)
        f_res.addRow("可靠度指标 (β):", self.lbl_beta)
        f_res.addRow("安全系数均值与标准差:", self.lbl_fs_mean_std)
        f_res.addRow("抽样极值范围 [Min, Max]:", self.lbl_fs_range)
        f_res.addRow("失效破坏样本统计:", self.lbl_fail_counts)
        grp_res.setLayout(f_res)
        layout.addWidget(grp_res)

        layout.addStretch()
        self.setWidget(container)

    def get_config(self) -> Dict[str, Any]:
        """提取界面控件参数供后端求解器使用"""
        return {
            "method": "MCS" if "蒙特卡洛" in self.combo_rel_method.currentText() else "PEM",
            "eval_method": "Bishop" if "Bishop" in self.combo_eval_method.currentText() else "Fellenius",
            "n_samples": self.spin_n_sim.value(),
            "cov_c": self.spin_cov_c.value(),
            "dist_c": self.combo_dist_c.currentText(),
            "cov_phi": self.spin_cov_phi.value(),
            "dist_phi": self.combo_dist_phi.currentText(),
            "rho": self.spin_rho.value(),
            "cov_gamma": self.spin_cov_gamma.value()
        }

    def display_results(self, res: Dict[str, Any]):
        """渲染呈现计算成果"""
        pf_pct = res.get("pf_percent", 0.0)
        beta = res.get("beta", 0.0)
        mean_fs = res.get("fs_mean", 0.0)
        std_fs = res.get("fs_std", 0.0)
        cov_fs = res.get("fs_cov", 0.0)

        self.lbl_pf.setText(f"{pf_pct:.2f}% (P_f = {res.get('pf', 0.0):.4e})")
        self.lbl_beta.setText(f"β = {beta:.3f}")
        self.lbl_fs_mean_std.setText(f"μ = {mean_fs:.3f}, σ = {std_fs:.3f} (COV={cov_fs:.2f})")

        if "fs_min" in res:
            self.lbl_fs_range.setText(f"[{res['fs_min']:.3f}, {res['fs_max']:.3f}]")
            self.lbl_fail_counts.setText(f"{res['failure_count']} 次失效 / {res['n_valid']} 次有效抽样")
        else:
            self.lbl_fs_range.setText("点估计法不提供极值样本")
            self.lbl_fail_counts.setText("解析点估计近似估算")
            
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rel_method": self.combo_rel_method.currentIndex(),
            "eval_method": self.combo_eval_method.currentIndex(),
            "n_samples": self.spin_n_sim.value(),
            "cov_c": self.spin_cov_c.value(),
            "dist_c": self.combo_dist_c.currentIndex(),
            "cov_phi": self.spin_cov_phi.value(),
            "dist_phi": self.combo_dist_phi.currentIndex(),
            "rho": self.spin_rho.value(),
            "cov_gamma": self.spin_cov_gamma.value(),
        }

    def from_dict(self, data: Dict[str, Any]):
        if not isinstance(data, dict):
            return
        if "rel_method" in data:   self.combo_rel_method.setCurrentIndex(int(data["rel_method"]))
        if "eval_method" in data:  self.combo_eval_method.setCurrentIndex(int(data["eval_method"]))
        if "n_samples" in data:    self.spin_n_sim.setValue(int(data["n_samples"]))
        if "cov_c" in data:        self.spin_cov_c.setValue(float(data["cov_c"]))
        if "dist_c" in data:       self.combo_dist_c.setCurrentIndex(int(data["dist_c"]))
        if "cov_phi" in data:      self.spin_cov_phi.setValue(float(data["cov_phi"]))
        if "dist_phi" in data:     self.combo_dist_phi.setCurrentIndex(int(data["dist_phi"]))
        if "rho" in data:          self.spin_rho.setValue(float(data["rho"]))
        if "cov_gamma" in data:    self.spin_cov_gamma.setValue(float(data["cov_gamma"]))