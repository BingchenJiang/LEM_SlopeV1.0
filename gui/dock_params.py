# -*- coding: utf-8 -*-
"""
几何、水力条件、材料、指定滑面与智能搜索控制面板 (PyQt5)
"""
from typing import List, Tuple, Dict, Any
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QDoubleSpinBox, QSpinBox, QComboBox, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
    QProgressBar
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

        # Tab 1: 几何与地下水位
        tab_geom = QWidget()
        layout_geom = QVBoxLayout(tab_geom)
        layout_geom.addWidget(QLabel("<b>边坡地面折线坐标点 (X, Y 单位: 米):</b>"))

        self.tbl_coords = QTableWidget(4, 2)
        self.tbl_coords.setHorizontalHeaderLabels(["X 坐标 (m)", "Y 高程 (m)"])
        default_pts = [(0.0, 15.0), (20.0, 15.0), (35.0, 0.0), (60.0, 0.0)]
        for r, (x, y) in enumerate(default_pts):
            self.tbl_coords.setItem(r, 0, QTableWidgetItem(str(x)))
            self.tbl_coords.setItem(r, 1, QTableWidgetItem(str(y)))
        self.tbl_coords.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout_geom.addWidget(self.tbl_coords)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("添加坐标点")
        btn_add.clicked.connect(self._add_point)
        btn_del = QPushButton("删除选中点")
        btn_del.clicked.connect(self._del_point)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        layout_geom.addLayout(btn_row)

        grp_water = QGroupBox("地下水孔隙水压力条件")
        form_water = QFormLayout()
        self.combo_water = QComboBox()
        self.combo_water.addItems(["干燥状态 (无水)", "孔压比系数 (ru)", "固定浸润线"])
        self.spin_ru = QDoubleSpinBox()
        self.spin_ru.setRange(0.0, 0.8)
        self.spin_ru.setSingleStep(0.05)
        self.spin_ru.setValue(0.0)
        form_water.addRow("水力模式:", self.combo_water)
        form_water.addRow("孔压比 ru:", self.spin_ru)
        grp_water.setLayout(form_water)
        layout_geom.addWidget(grp_water)
        layout_geom.addStretch()
        self.tabs.addTab(tab_geom, "几何外形与水力")

        # Tab 2: 土性与指定滑弧
        tab_soil = QWidget()
        layout_soil = QVBoxLayout(tab_soil)

        grp_mat = QGroupBox("莫尔-库仑土体抗剪强度参数")
        form_mat = QFormLayout()
        self.spin_gamma = QDoubleSpinBox()
        self.spin_gamma.setRange(5.0, 40.0)
        self.spin_gamma.setValue(20.0)
        self.spin_gamma.setSuffix(" kN/m³")

        self.spin_c = QDoubleSpinBox()
        self.spin_c.setRange(0.0, 300.0)
        self.spin_c.setValue(15.0)
        self.spin_c.setSuffix(" kPa")

        self.spin_phi = QDoubleSpinBox()
        self.spin_phi.setRange(0.0, 50.0)
        self.spin_phi.setValue(20.0)
        self.spin_phi.setSuffix(" °")

        form_mat.addRow("天然重度 (γ):", self.spin_gamma)
        form_mat.addRow("有效黏聚力 (c'):", self.spin_c)
        form_mat.addRow("内摩擦角 (φ'):", self.spin_phi)
        grp_mat.setLayout(form_mat)
        layout_soil.addWidget(grp_mat)

        grp_circle = QGroupBox("指定试算滑弧与切片网格")
        form_circle = QFormLayout()
        self.spin_xc = QDoubleSpinBox()
        self.spin_xc.setRange(-200.0, 200.0)
        self.spin_xc.setValue(25.0)
        self.spin_xc.setSuffix(" m")

        self.spin_yc = QDoubleSpinBox()
        self.spin_yc.setRange(-200.0, 200.0)
        self.spin_yc.setValue(22.0)
        self.spin_yc.setSuffix(" m")

        self.spin_r = QDoubleSpinBox()
        self.spin_r.setRange(1.0, 300.0)
        self.spin_r.setValue(23.0)
        self.spin_r.setSuffix(" m")

        self.spin_slices = QSpinBox()
        self.spin_slices.setRange(10, 150)
        self.spin_slices.setValue(30)
        self.spin_slices.setSuffix(" 个")

        form_circle.addRow("滑弧圆心 X (xc):", self.spin_xc)
        form_circle.addRow("滑弧圆心 Y (yc):", self.spin_yc)
        form_circle.addRow("滑弧半径 (R):", self.spin_r)
        form_circle.addRow("离散土条数量 (N):", self.spin_slices)
        grp_circle.setLayout(form_circle)
        layout_soil.addWidget(grp_circle)

        btn_preview = QPushButton("刷新几何与条分网格")
        btn_preview.clicked.connect(self.params_changed.emit)
        layout_soil.addWidget(btn_preview)
        layout_soil.addStretch()
        self.tabs.addTab(tab_soil, "土性与试算滑面")

        # Tab 3: 经典与高等优化搜索算法
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
        self.btn_search.setStyleSheet(
            "background-color: #d35400; color: white; font-weight: bold; font-size: 13px; padding: 7px; border-radius: 4px;"
        )
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
        self.prog_bar.setTextVisible(True)
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
        self.btn_run.setStyleSheet(
            "background-color: #27ae60; color: white; font-weight: bold; font-size: 13px; padding: 10px; border-radius: 4px;"
        )
        self.btn_run.clicked.connect(self.calculate_requested.emit)
        layout.addWidget(self.btn_run)

    def _add_point(self):
        row = self.tbl_coords.rowCount()
        self.tbl_coords.insertRow(row)
        self.tbl_coords.setItem(row, 0, QTableWidgetItem("0.0"))
        self.tbl_coords.setItem(row, 1, QTableWidgetItem("0.0"))

    def _del_point(self):
        r = self.tbl_coords.currentRow()
        if r >= 0 and self.tbl_coords.rowCount() > 2:
            self.tbl_coords.removeRow(r)

    def set_geometry_data(self, pts: List[Tuple[float, float]]):
        self.tbl_coords.setRowCount(len(pts))
        for r, (x, y) in enumerate(pts):
            self.tbl_coords.setItem(r, 0, QTableWidgetItem(str(round(x, 3))))
            self.tbl_coords.setItem(r, 1, QTableWidgetItem(str(round(y, 3))))

    def get_geometry_data(self) -> Tuple[List[float], List[float], List[Tuple[float, float]]]:
        gx, gy = [], []
        for r in range(self.tbl_coords.rowCount()):
            ix = self.tbl_coords.item(r, 0)
            iy = self.tbl_coords.item(r, 1)
            if ix and iy:
                try:
                    gx.append(float(ix.text()))
                    gy.append(float(iy.text()))
                except ValueError:
                    pass
        pairs = sorted(zip(gx, gy), key=lambda p: p[0])
        return [p[0] for p in pairs], [p[1] for p in pairs], pairs

    def get_material(self) -> SoilMaterial:
        return SoilMaterial(
            name="均质土层",
            gamma=self.spin_gamma.value(),
            c=self.spin_c.value(),
            phi_deg=self.spin_phi.value()
        )

    def set_material(self, gamma: float, c: float, phi_deg: float):
        self.spin_gamma.setValue(gamma)
        self.spin_c.setValue(c)
        self.spin_phi.setValue(phi_deg)

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

    def get_water_condition(self) -> Tuple[float, bool]:
        mode = self.combo_water.currentText()
        if "ru" in mode:
            return self.spin_ru.value(), False
        elif "浸润线" in mode:
            return 0.0, True
        return 0.0, False

    def set_water_condition(self, mode_str: str, ru: float):
        idx = self.combo_water.findText(mode_str)
        if idx >= 0:
            self.combo_water.setCurrentIndex(idx)
        self.spin_ru.setValue(ru)

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
        _, _, pts = self.get_geometry_data()
        xc, yc, R, n_slices = self.get_circle_params()
        ru, use_water = self.get_water_condition()
        return {
            "ground_points": pts,
            "soil": {
                "gamma": self.spin_gamma.value(),
                "c": self.spin_c.value(),
                "phi_deg": self.spin_phi.value()
            },
            "slip_circle": {
                "xc": xc, "yc": yc, "R": R, "n_slices": n_slices
            },
            "water": {
                "mode": self.combo_water.currentText(),
                "ru": ru
            }
        }

    def from_dict(self, data: Dict[str, Any]):
        if "ground_points" in data:
            self.set_geometry_data(data["ground_points"])
        if "soil" in data:
            s = data["soil"]
            self.set_material(s.get("gamma", 20.0), s.get("c", 15.0), s.get("phi_deg", 20.0))
        if "slip_circle" in data:
            c = data["slip_circle"]
            self.set_circle_params(c.get("xc", 25.0), c.get("yc", 22.0), c.get("R", 23.0))
            if "n_slices" in c:
                self.spin_slices.setValue(c["n_slices"])
        if "water" in data:
            w = data["water"]
            self.set_water_condition(w.get("mode", "干燥状态 (无水)"), w.get("ru", 0.0))