# -*- coding: utf-8 -*-
"""
边坡极限平衡法稳定性分析平台 (LEM-Slope-Studio)
应用程序入口
"""
import sys
try:
    from PyQt5.QtWidgets import QApplication
except ImportError:
    from PyQt6.QtWidgets import QApplication

from gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 设置应用程序的样式为 Fusion，提供一致的外观
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()