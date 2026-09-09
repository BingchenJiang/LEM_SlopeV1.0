# -*- coding: utf-8 -*-
"""
综合控制面板 (PyQt5)
集成独立浸润线、多层地层材料库、非饱和吸力参数、降雨入渗湿润锋、坡顶外荷载与拟静力地震工况
"""
from typing import List, Optional, Tuple, Dict, Any
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QDoubleSpinBox, QSpinBox, QComboBox, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
    QProgressBar, QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal

from core.materials import SoilMaterial


class ParamsDockWidget(QWidget):
    params_changed = pyqtSignal()
    calculate_requested = pyqtSignal()
    search_requested = pyqtSignal()
    search_stop_requested = pyqtSignal()
    apply_searched_circle = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        # Tab 1: 几何外形与地下水位
        tab_geom = QWidget()
        layout_geom = QVBoxLayout(tab_geom)

        layout_geom.addWidget(QLabel("<b>边坡地面折线坐标点 (X, Y 单位: 米):</b>"))
        self.tbl_ground = QTableWidget(4, 2)
        self.tbl_ground.setHorizontalHeaderLabels(["X 坐标 (m)", "Y 高程 (m)"])
        default_ground = [(0.0, 15.0), (20.0, 15.0), (35.0, 0.0), (60.0, 0.0)]
        for r, (x, y) in enumerate(default_ground):
            self.tbl_ground.setItem(r, 0, QTableWidgetItem(str(x)))
            self.tbl_ground.setItem(r, 1, QTableWidgetItem(str(y)))
        self.tbl_ground.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout_geom.addWidget(self.tbl_ground)

        btn_g_row = QHBoxLayout()
        btn_g_add = QPushButton("添加地表点")
        btn_g_add.clicked.connect(lambda: self._add_table_row(self.tbl_ground))
        btn_g_del = QPushButton("删除选中点")
        btn_g_del.clicked.connect(lambda: self._del_table_row(self.tbl_ground))
        btn_g_row.addWidget(btn_g_add)
        btn_g_row.addWidget(btn_g_del)
        layout_geom.addLayout(btn_g_row)

        grp_water = QGroupBox("地下水浸润线 (Piezometric Line)")
        layout_water = QVBoxLayout(grp_water)
        self.chk_use_water = QCheckBox("启用地下水浸润线")
        self.chk_use_water.setChecked(True)
        self.chk_use_water.stateChanged.connect(self.params_changed.emit)
        layout_water.addWidget(self.chk_use_water)

        self.tbl_water = QTableWidget(4, 2)
        self.tbl_water.setHorizontalHeaderLabels(["X 坐标 (m)", "水位 Y (m)"])
        default_water = [(0.0, 12.0), (20.0, 12.0), (35.0, -1.0), (60.0, -1.0)]
        for r, (x, y) in enumerate(default_water):
            self.tbl_water.setItem(r, 0, QTableWidgetItem(str(x)))
            self.tbl_water.setItem(r, 1, QTableWidgetItem(str(y)))
        self.tbl_water.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout_water.addWidget(self.tbl_water)

        btn_w_row = QHBoxLayout()
        btn_w_add = QPushButton("添加水位点")
        btn_w_add.clicked.connect(lambda: self._add_table_row(self.tbl_water))
        btn_w_del = QPushButton("删除水位点")
        btn_w_del.clicked.connect(lambda: self._del_table_row(self.tbl_water))
        btn_w_row.addWidget(btn_w_add)
        btn_w_row.addWidget(btn_w_del)
        layout_water.addLayout(btn_w_row)

        layout_geom.addWidget(grp_water)
        layout_geom.addStretch()
        self.tabs.addTab(tab_geom, "几何与地下水")

        # Tab 2: 多层地层与非饱和本构
        tab_strata = QWidget()
        layout_strata = QVBoxLayout(tab_strata)

        grp_layer1 = QGroupBox("第 1 层：上部覆土/残积土")
        form_l1 = QFormLayout()
        self.spin_g1_dry = QDoubleSpinBox(); self.spin_g1_dry.setValue(19.0); self.spin_g1_dry.setSuffix(" kN/m3")
        self.spin_g1_sat = QDoubleSpinBox(); self.spin_g1_sat.setValue(21.0); self.spin_g1_sat.setSuffix(" kN/m3")
        self.spin_c1 = QDoubleSpinBox(); self.spin_c1.setValue(15.0); self.spin_c1.setSuffix(" kPa")
        self.spin_phi1 = QDoubleSpinBox(); self.spin_phi1.setValue(20.0); self.spin_phi1.setSuffix(" °")
        self.spin_phib1 = QDoubleSpinBox(); self.spin_phib1.setValue(15.0); self.spin_phib1.setSuffix(" °")
        self.spin_cutoff1 = QDoubleSpinBox(); self.spin_cutoff1.setRange(0, 500); self.spin_cutoff1.setValue(100.0); self.spin_cutoff1.setSuffix(" kPa")
        form_l1.addRow("天然重度 (γ):", self.spin_g1_dry)
        form_l1.addRow("饱和重度 (γsat):", self.spin_g1_sat)
        form_l1.addRow("有效黏聚力 (c'):", self.spin_c1)
        form_l1.addRow("有效摩擦角 (φ'):", self.spin_phi1)
        form_l1.addRow("非饱和吸力角 (φb):", self.spin_phib1)
        form_l1.addRow("基质吸力上限截断值:", self.spin_cutoff1)
        grp_layer1.setLayout(form_l1)
        layout_strata.addWidget(grp_layer1)

        grp_layer2 = QGroupBox("第 2 层：下卧基岩/坚硬层")
        form_l2 = QFormLayout()
        self.chk_use_layer2 = QCheckBox("启用下卧第二层地层分界")
        self.chk_use_layer2.setChecked(True)
        self.chk_use_layer2.stateChanged.connect(self.params_changed.emit)
        form_l2.addRow(self.chk_use_layer2)

        self.spin_g2_dry = QDoubleSpinBox(); self.spin_g2_dry.setValue(22.0); self.spin_g2_dry.setSuffix(" kN/m3")
        self.spin_g2_sat = QDoubleSpinBox(); self.spin_g2_sat.setValue(23.5); self.spin_g2_sat.setSuffix(" kN/m3")
        self.spin_c2 = QDoubleSpinBox(); self.spin_c2.setValue(45.0); self.spin_c2.setSuffix(" kPa")
        self.spin_phi2 = QDoubleSpinBox(); self.spin_phi2.setValue(32.0); self.spin_phi2.setSuffix(" °")
        self.spin_phib2 = QDoubleSpinBox(); self.spin_phib2.setValue(25.0); self.spin_phib2.setSuffix(" °")
        self.spin_cutoff2 = QDoubleSpinBox(); self.spin_cutoff2.setRange(0, 500); self.spin_cutoff2.setValue(150.0); self.spin_cutoff2.setSuffix(" kPa")
        self.spin_strata2_y = QDoubleSpinBox(); self.spin_strata2_y.setRange(-50, 50); self.spin_strata2_y.setValue(6.0); self.spin_strata2_y.setSuffix(" m")
        form_l2.addRow("分界面水平标高 Y:", self.spin_strata2_y)
        form_l2.addRow("天然重度 (γ):", self.spin_g2_dry)
        form_l2.addRow("饱和重度 (γsat):", self.spin_g2_sat)
        form_l2.addRow("有效黏聚力 (c'):", self.spin_c2)
        form_l2.addRow("有效摩擦角 (φ'):", self.spin_phi2)
        form_l2.addRow("非饱和吸力角 (φb):", self.spin_phib2)
        form_l2.addRow("基质吸力上限截断值:", self.spin_cutoff2)
        grp_layer2.setLayout(form_l2)
        layout_strata.addWidget(grp_layer2)
        layout_strata.addStretch()
        self.tabs.addTab(tab_strata, "多层地层与非饱和土")

        # Tab 3: 降雨入渗、外载与地震
        tab_env = QWidget()
        layout_env = QVBoxLayout(tab_env)

        grp_rain = QGroupBox("降雨入渗弱化工况")
        form_rain = QFormLayout()
        self.spin_rain_depth = QDoubleSpinBox()
        self.spin_rain_depth.setRange(0.0, 30.0)
        self.spin_rain_depth.setValue(0.0)
        self.spin_rain_depth.setSingleStep(0.5)
        self.spin_rain_depth.setSuffix(" m")
        form_rain.addRow("降雨入渗湿润锋深度:", self.spin_rain_depth)
        grp_rain.setLayout(form_rain)
        layout_env.addWidget(grp_rain)

        grp_load = QGroupBox("坡顶附加均布荷载")
        form_load = QFormLayout()
        self.spin_q = QDoubleSpinBox(); self.spin_q.setRange(0.0, 500.0); self.spin_q.setValue(0.0); self.spin_q.setSuffix(" kPa")
        self.spin_qx1 = QDoubleSpinBox(); self.spin_qx1.setRange(-50, 100); self.spin_qx1.setValue(5.0); self.spin_qx1.setSuffix(" m")
        self.spin_qx2 = QDoubleSpinBox(); self.spin_qx2.setRange(-50, 100); self.spin_qx2.setValue(18.0); self.spin_qx2.setSuffix(" m")
        form_load.addRow("附加荷载强度 (q):", self.spin_q)
        form_load.addRow("荷载起始水平位置 X1:", self.spin_qx1)
        form_load.addRow("荷载终止水平位置 X2:", self.spin_qx2)
        grp_load.setLayout(form_load)
        layout_env.addWidget(grp_load)

        grp_seismic = QGroupBox("地震动作用 (拟静力法)")
        form_seismic = QFormLayout()
        self.spin_kh = QDoubleSpinBox()
        self.spin_kh.setRange(0.0, 0.4)
        self.spin_kh.setValue(0.0)
        self.spin_kh.setSingleStep(0.02)
        form_seismic.addRow("水平地震力系数 (kh):", self.spin_kh)
        grp_seismic.setLayout(form_seismic)
        layout_env.addWidget(grp_seismic)

        layout_env.addStretch()
        self.tabs.addTab(tab_env, "降雨外载与地震")

        # Tab 4: 试算滑弧与切片
        tab_circle = QWidget()
        layout_circle = QVBoxLayout(tab_circle)

        grp_circle = QGroupBox("指定试算滑弧与切片网格")
        form_circle = QFormLayout()
        self.spin_xc = QDoubleSpinBox(); self.spin_xc.setRange(-200.0, 200.0); self.spin_xc.setValue(25.0); self.spin_xc.setSuffix(" m")
        self.spin_yc = QDoubleSpinBox(); self.spin_yc.setRange(-200.0, 200.0); self.spin_yc.setValue(22.0); self.spin_yc.setSuffix(" m")
        self.spin_r = QDoubleSpinBox(); self.spin_r.setRange(1.0, 300.0); self.spin_r.setValue(23.0); self.spin_r.setSuffix(" m")
        self.spin_slices = QSpinBox(); self.spin_slices.setRange(10, 150); self.spin_slices.setValue(30); self.spin_slices.setSuffix(" 个")
        form_circle.addRow("滑弧圆心 X (xc):", self.spin_xc)
        form_circle.addRow("滑弧圆心 Y (yc):", self.spin_yc)
        form_circle.addRow("滑弧半径 (R):", self.spin_r)
        form_circle.addRow("离散土条数量 (N):", self.spin_slices)
        grp_circle.setLayout(form_circle)
        layout_circle.addWidget(grp_circle)

        btn_preview = QPushButton("刷新几何模型与条分切片")
        btn_preview.clicked.connect(self.params_changed.emit)
        layout_circle.addWidget(btn_preview)
        layout_circle.addStretch()
        self.tabs.addTab(tab_circle, "试算滑弧网格")

        # Tab 5: 临界滑面全局寻优
        tab_search = QWidget()
        layout_search = QVBoxLayout(tab_search)

        grp_algo = QGroupBox("滑面智能全局寻优设置")
        form_algo = QFormLayout()
        self.combo_algo = QComboBox()
        self.combo_algo.addItems([
            "粒子群优化算法 (PSO)",
            "模拟退火算法 (Simulated Annealing)",
            "差分进化算法 (Differential Evolution)",
            "单纯形搜索法 (Nelder-Mead)",
            "经典网格扫描法 (Grid Search)"
        ])
        self.combo_search_eval = QComboBox()
        self.combo_search_eval.addItems(["Simplified Bishop (推荐/高效)", "Fellenius / Ordinary"])
        form_algo.addRow("寻优搜索算法:", self.combo_algo)
        form_algo.addRow("目标评估模型:", self.combo_search_eval)
        grp_algo.setLayout(form_algo)
        layout_search.addWidget(grp_algo)

        grp_bounds = QGroupBox("滑弧搜索几何包络空间")
        form_bounds = QFormLayout()
        self.spin_xmin = QDoubleSpinBox(); self.spin_xmin.setRange(-100, 200); self.spin_xmin.setValue(10.0)
        self.spin_xmax = QDoubleSpinBox(); self.spin_xmax.setRange(-100, 200); self.spin_xmax.setValue(45.0)
        self.spin_ymin = QDoubleSpinBox(); self.spin_ymin.setRange(-100, 200); self.spin_ymin.setValue(15.0)
        self.spin_ymax = QDoubleSpinBox(); self.spin_ymax.setRange(-100, 200); self.spin_ymax.setValue(40.0)
        self.spin_rmin = QDoubleSpinBox(); self.spin_rmin.setRange(1.0, 300); self.spin_rmin.setValue(10.0)
        self.spin_rmax = QDoubleSpinBox(); self.spin_rmax.setRange(1.0, 300); self.spin_rmax.setValue(45.0)

        h_x = QHBoxLayout(); h_x.addWidget(self.spin_xmin); h_x.addWidget(QLabel("~")); h_x.addWidget(self.spin_xmax)
        h_y = QHBoxLayout(); h_y.addWidget(self.spin_ymin); h_y.addWidget(QLabel("~")); h_y.addWidget(self.spin_ymax)
        h_r = QHBoxLayout(); h_r.addWidget(self.spin_rmin); h_r.addWidget(QLabel("~")); h_r.addWidget(self.spin_rmax)
        form_bounds.addRow("圆心 Xc 范围 (m):", h_x)
        form_bounds.addRow("圆心 Yc 范围 (m):", h_y)
        form_bounds.addRow("半径 R 范围 (m):", h_r)
        grp_bounds.setLayout(form_bounds)
        layout_search.addWidget(grp_bounds)

        search_btn_layout = QHBoxLayout()
        self.btn_search = QPushButton("启动最危险滑面搜索")
        self.btn_search.setStyleSheet("background-color: #d35400; color: white; font-weight: bold; font-size: 13px; padding: 7px; border-radius: 4px;")
        self.btn_search.clicked.connect(self.search_requested.emit)

        self.btn_stop_search = QPushButton("终止搜索")
        self.btn_stop_search.setEnabled(False)
        self.btn_stop_search.setStyleSheet("padding: 7px;")
        self.btn_stop_search.clicked.connect(self.search_stop_requested.emit)

        search_btn_layout.addWidget(self.btn_search)
        search_btn_layout.addWidget(self.btn_stop_search)
        layout_search.addLayout(search_btn_layout)

        self.prog_bar = QProgressBar()
        self.prog_bar.setValue(0)
        layout_search.addWidget(self.prog_bar)

        grp_res_card = QGroupBox("临界滑弧寻优结果")
        form_res_card = QFormLayout()
        self.lbl_best_circle = QLabel("未搜索")
        self.lbl_best_fs = QLabel("未搜索")
        self.lbl_best_fs.setStyleSheet("font-weight: bold; color: #c0392b; font-size: 14px;")
        form_res_card.addRow("最危险滑弧参数:", self.lbl_best_circle)
        form_res_card.addRow("最小安全系数 (min Fs):", self.lbl_best_fs)
        grp_res_card.setLayout(form_res_card)
        layout_search.addWidget(grp_res_card)

        self.btn_apply = QPushButton("应用最危险滑面至主模型")
        self.btn_apply.clicked.connect(self.apply_searched_circle.emit)
        layout_search.addWidget(self.btn_apply)

        layout_search.addStretch()
        self.tabs.addTab(tab_search, "临界滑面智能搜索")

        layout.addWidget(self.tabs)

        self.btn_run = QPushButton("运行全部经典土力学模型求解")
        self.btn_run.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; font-size: 13px; padding: 10px; border-radius: 4px;")
        self.btn_run.clicked.connect(self.calculate_requested.emit)
        layout.addWidget(self.btn_run)

    def _add_table_row(self, table: QTableWidget):
        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row, 0, QTableWidgetItem("0.0"))
        table.setItem(row, 1, QTableWidgetItem("0.0"))

    def _del_table_row(self, table: QTableWidget):
        r = table.currentRow()
        if r >= 0 and table.rowCount() > 2:
            table.removeRow(r)

    def get_geometry_data(self) -> Tuple[List[float], List[float], List[Tuple[float, float]]]:
        gx, gy = [], []
        for r in range(self.tbl_ground.rowCount()):
            ix = self.tbl_ground.item(r, 0)
            iy = self.tbl_ground.item(r, 1)
            if ix and iy:
                try:
                    gx.append(float(ix.text()))
                    gy.append(float(iy.text()))
                except ValueError:
                    pass
        pairs = sorted(zip(gx, gy), key=lambda p: p[0])
        return [p[0] for p in pairs], [p[1] for p in pairs], pairs

    def set_geometry_data(self, pts: List[Tuple[float, float]]):
        self.tbl_ground.setRowCount(len(pts))
        for r, (x, y) in enumerate(pts):
            self.tbl_ground.setItem(r, 0, QTableWidgetItem(str(round(x, 3))))
            self.tbl_ground.setItem(r, 1, QTableWidgetItem(str(round(y, 3))))

    def get_water_data(self) -> Optional[List[Tuple[float, float]]]:
        if not self.chk_use_water.isChecked():
            return None
        wx, wy = [], []
        for r in range(self.tbl_water.rowCount()):
            ix = self.tbl_water.item(r, 0)
            iy = self.tbl_water.item(r, 1)
            if ix and iy:
                try:
                    wx.append(float(ix.text()))
                    wy.append(float(iy.text()))
                except ValueError:
                    pass
        if len(wx) < 2:
            return None
        return sorted(zip(wx, wy), key=lambda p: p[0])

    def get_strata_boundaries(self) -> List[List[Tuple[float, float]]]:
        if not self.chk_use_layer2.isChecked():
            return []
        _, _, g_pts = self.get_geometry_data()
        if not g_pts:
            return []
        strata_y = self.spin_strata2_y.value()
        line = [(g_pts[0][0] - 10.0, strata_y), (g_pts[-1][0] + 10.0, strata_y)]
        return [line]

    def get_materials(self) -> List[SoilMaterial]:
        mat1 = SoilMaterial(
            name="第1层-覆盖土",
            gamma_dry=self.spin_g1_dry.value(),
            gamma_sat=self.spin_g1_sat.value(),
            c_prime=self.spin_c1.value(),
            phi_deg=self.spin_phi1.value(),
            phi_b_deg=self.spin_phib1.value(),
            suction_cutoff=self.spin_cutoff1.value()
        )
        if not self.chk_use_layer2.isChecked():
            return [mat1]

        mat2 = SoilMaterial(
            name="第2层-基岩层",
            gamma_dry=self.spin_g2_dry.value(),
            gamma_sat=self.spin_g2_sat.value(),
            c_prime=self.spin_c2.value(),
            phi_deg=self.spin_phi2.value(),
            phi_b_deg=self.spin_phib2.value(),
            suction_cutoff=self.spin_cutoff2.value()
        )
        return [mat1, mat2]

    def get_env_conditions(self) -> Tuple[float, float, List[Tuple[float, float, float]]]:
        rain_d = self.spin_rain_depth.value()
        kh = self.spin_kh.value()
        q_val = self.spin_q.value()
        surcharge = []
        if q_val > 0.0:
            surcharge.append((self.spin_qx1.value(), self.spin_qx2.value(), q_val))
        return rain_d, kh, surcharge

    def get_circle_params(self) -> Tuple[float, float, float, int]:
        return (
            self.spin_xc.value(),
            self.spin_yc.value(),
            self.spin_r.value(),
            self.spin_slices.value()
        )

    def set_circle_params(self, xc: float, yc: float, R: float):
        self.spin_xc.setValue(xc)
        self.spin_yc.setValue(yc)
        self.spin_r.setValue(R)

    def get_search_config(self):
        algo_name = self.combo_algo.currentText()
        eval_name = "Bishop" if "Bishop" in self.combo_search_eval.currentText() else "Fellenius"
        bounds = [
            (self.spin_xmin.value(), self.spin_xmax.value()),
            (self.spin_ymin.value(), self.spin_ymax.value()),
            (self.spin_rmin.value(), self.spin_rmax.value()),
        ]
        return algo_name, eval_name, bounds

    def to_dict(self) -> Dict[str, Any]:
        _, _, g_pts = self.get_geometry_data()
        w_pts = self.get_water_data()
        xc, yc, R, n_slices = self.get_circle_params()
        rain_d, kh, sur = self.get_env_conditions()
        return {
            "ground_points": g_pts,
            "water_points": w_pts,
            "use_water": self.chk_use_water.isChecked(),
            "use_layer2": self.chk_use_layer2.isChecked(),
            "layer2_y": self.spin_strata2_y.value(),
            "layer1": {
                "gamma_dry": self.spin_g1_dry.value(),
                "gamma_sat": self.spin_g1_sat.value(),
                "c": self.spin_c1.value(),
                "phi": self.spin_phi1.value(),
                "phib": self.spin_phib1.value(),
                "cutoff": self.spin_cutoff1.value()
            },
            "layer2": {
                "gamma_dry": self.spin_g2_dry.value(),
                "gamma_sat": self.spin_g2_sat.value(),
                "c": self.spin_c2.value(),
                "phi": self.spin_phi2.value(),
                "phib": self.spin_phib2.value(),
                "cutoff": self.spin_cutoff2.value()
            },
            "environment": {
                "rain_depth": rain_d,
                "kh": kh,
                "surcharge": sur
            },
            "slip_circle": {
                "xc": xc, "yc": yc, "R": R, "n_slices": n_slices
            }
        }

    def from_dict(self, data: Dict[str, Any]):
        if "ground_points" in data:
            self.set_geometry_data(data["ground_points"])
        if "water_points" in data and data["water_points"]:
            self.tbl_water.setRowCount(len(data["water_points"]))
            for r, (x, y) in enumerate(data["water_points"]):
                self.tbl_water.setItem(r, 0, QTableWidgetItem(str(round(x, 3))))
                self.tbl_water.setItem(r, 1, QTableWidgetItem(str(round(y, 3))))
        if "use_water" in data:
            self.chk_use_water.setChecked(data["use_water"])
        if "use_layer2" in data:
            self.chk_use_layer2.setChecked(data["use_layer2"])
        if "layer2_y" in data:
            self.spin_strata2_y.setValue(data["layer2_y"])
        if "layer1" in data:
            l1 = data["layer1"]
            self.spin_g1_dry.setValue(l1.get("gamma_dry", 19.0))
            self.spin_g1_sat.setValue(l1.get("gamma_sat", 21.0))
            self.spin_c1.setValue(l1.get("c", 15.0))
            self.spin_phi1.setValue(l1.get("phi", 20.0))
            self.spin_phib1.setValue(l1.get("phib", 15.0))
            self.spin_cutoff1.setValue(l1.get("cutoff", 100.0))
        if "layer2" in data:
            l2 = data["layer2"]
            self.spin_g2_dry.setValue(l2.get("gamma_dry", 22.0))
            self.spin_g2_sat.setValue(l2.get("gamma_sat", 23.5))
            self.spin_c2.setValue(l2.get("c", 45.0))
            self.spin_phi2.setValue(l2.get("phi", 32.0))
            self.spin_phib2.setValue(l2.get("phib", 25.0))
            self.spin_cutoff2.setValue(l2.get("cutoff", 150.0))
        if "environment" in data:
            env = data["environment"]
            self.spin_rain_depth.setValue(env.get("rain_depth", 0.0))
            self.spin_kh.setValue(env.get("kh", 0.0))
            sur = env.get("surcharge", [])
            if sur:
                self.spin_qx1.setValue(sur[0][0])
                self.spin_qx2.setValue(sur[0][1])
                self.spin_q.setValue(sur[0][2])
        if "slip_circle" in data:
            c = data["slip_circle"]
            self.set_circle_params(c.get("xc", 25.0), c.get("yc", 22.0), c.get("R", 23.0))
            if "n_slices" in c:
                self.spin_slices.setValue(c["n_slices"])
