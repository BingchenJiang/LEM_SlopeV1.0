# -*- coding: utf-8 -*-
"""
安全系数对比汇总与条块受力物理量呈现面板
"""
from typing import List, Tuple, Optional
import numpy as np

try:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
        QHeaderView, QTabWidget
    )
    from PyQt5.QtCore import Qt
except ImportError:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
        QHeaderView, QTabWidget
    )
    from PyQt6.QtCore import Qt

from core.slicing import Slice


class ResultsDockWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        # Tab 1: 汇总对比表
        self.tbl_summary = QTableWidget(5, 3)
        self.tbl_summary.setHorizontalHeaderLabels(["极限平衡求解方法", "稳定安全系数 (Fs)", "力学平衡条件与收敛状态"])
        header_mode = QHeaderView.ResizeMode.Stretch if hasattr(QHeaderView, 'ResizeMode') else QHeaderView.Stretch
        self.tbl_summary.horizontalHeader().setSectionResizeMode(header_mode)
        self.tabs.addTab(self.tbl_summary, "经典 LEM 模型结果对比")

        # Tab 2: 土条微元受力明细表
        self.tbl_slices = QTableWidget(0, 8)
        self.tbl_slices.setHorizontalHeaderLabels([
            "条块号", "中点 X (m)", "条宽 b (m)", "高度 h (m)", "自重 W (kN)", "底坡角 α (°)", "孔压 u (kPa)", "底斜长 l (m)"
        ])
        self.tbl_slices.horizontalHeader().setSectionResizeMode(header_mode)
        self.tabs.addTab(self.tbl_slices, "离散土条切片物理量明细")

        layout.addWidget(self.tabs)

    def display_summary(self, results: List[Tuple[str, Tuple[Optional[float], str]]]):
        self.tbl_summary.setRowCount(len(results))
        for r, (method_name, (fs, note)) in enumerate(results):
            self.tbl_summary.setItem(r, 0, QTableWidgetItem(method_name))
            fs_text = f"{fs:.4f}" if fs is not None else "未收敛"
            item_fs = QTableWidgetItem(fs_text)
            align_center = Qt.AlignmentFlag.AlignCenter if hasattr(Qt, 'AlignmentFlag') else Qt.AlignCenter
            item_fs.setTextAlignment(align_center)
            self.tbl_summary.setItem(r, 1, item_fs)
            self.tbl_summary.setItem(r, 2, QTableWidgetItem(note))

    def display_slices(self, slices: Optional[List[Slice]]):
        if not slices:
            self.tbl_slices.setRowCount(0)
            return

        self.tbl_slices.setRowCount(len(slices))
        for r, s in enumerate(slices):
            self.tbl_slices.setItem(r, 0, QTableWidgetItem(str(s.index)))
            self.tbl_slices.setItem(r, 1, QTableWidgetItem(f"{s.xm:.2f}"))
            self.tbl_slices.setItem(r, 2, QTableWidgetItem(f"{s.b:.2f}"))
            self.tbl_slices.setItem(r, 3, QTableWidgetItem(f"{s.h:.2f}"))
            self.tbl_slices.setItem(r, 4, QTableWidgetItem(f"{s.W:.2f}"))
            self.tbl_slices.setItem(r, 5, QTableWidgetItem(f"{np.degrees(s.alpha):.2f}"))
            self.tbl_slices.setItem(r, 6, QTableWidgetItem(f"{s.u:.2f}"))
            self.tbl_slices.setItem(r, 7, QTableWidgetItem(f"{s.l:.2f}"))