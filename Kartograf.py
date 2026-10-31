import sys
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableView, QTabWidget, QLineEdit, QPushButton, QLabel
)

C = 28

class Canvas(QWidget):
    def __init__(self):
        super().__init__()
        self.w = 20
        self.h = 15
        self.setMinimumSize(
            self.w * C + 2,
            self.h * C + 2
        )

    # def paintEvent(self, event):



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Картограф — прототип")
        self.resize(1100, 700)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.build_levels()
        self.build_editor()

    def build_levels(self):
        self.table = QTableView()

        open_btn = QPushButton("Открыть")
        new_btn = QPushButton("Новый")

        t = QWidget()
        l = QVBoxLayout(t)
        l.addWidget(self.table)
        l.addWidget(open_btn)
        l.addWidget(new_btn)
        self.tabs.addTab(t, "Уровни")

    def build_editor(self):
        self.editor = QWidget()
        l = QHBoxLayout(self.editor)

        tools = QVBoxLayout()
        tools.addWidget(QLabel("Инструменты:"))

        for name in ["Стена", "Старт", "Финиш", "Враг", "Ластик"]:
            tools.addWidget(QPushButton(name))

        tools.addStretch()
        tools.addWidget(QPushButton("Найти путь"))
        tools.addWidget(QPushButton("Статистика"))

        self.canvas = Canvas()

        l.addLayout(tools)
        l.addWidget(self.canvas, 1)
        self.tabs.addTab(self.editor, "Редактор")




if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())