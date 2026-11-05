import sys
import sqlite3
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QTabWidget, QLineEdit, QPushButton,
    QLabel, QMessageBox, QInputDialog
)

# добвить инструменты и сохранине файлов/пнг

DB = "cartographer.sqlite"
C = 28

def init_db():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS levels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        width INTEGER NOT NULL,
        height INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS tiles (
        level_id INTEGER NOT NULL,
        x INTEGER NOT NULL,
        y INTEGER NOT NULL,
        kind TEXT NOT NULL,
        PRIMARY KEY (level_id, x, y),
        FOREIGN KEY (level_id) REFERENCES levels(id) ON DELETE CASCADE
    );
    """)
    con.commit()
    con.close()

class Canvas(QWidget):
    def __init__(self):
        super().__init__()
        self.w = 20
        self.h = 15
        self.setMinimumSize(self.w * C + 2, self.h * C + 2)

    def set_level(self, width, height):
        self.w = width
        self.h = height
        self.setMinimumSize(self.w * C + 2, self.h * C + 2)
        self.update()

    def paintEvent(self, event):
        qp = QPainter()
        qp.begin(self)
        qp.fillRect(self.rect(), QColor("#fafafa"))
        qp.setPen(QPen(QColor("#ddd"), 1))
        for x in range(self.w + 1):
            qp.drawLine(x * C, 0, x * C, self.h * C)
        for y in range(self.h + 1):
            qp.drawLine(0, y * C, self.w * C, y * C)
        qp.end()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Картограф — прототип 2")
        self.resize(1100, 700)

        self.con = sqlite3.connect(DB)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.build_levels()
        self.build_editor()

    def build_levels(self):
        self.table = QTableWidget()
        self.table.setSortingEnabled(True)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск...")
        self.search.textChanged.connect(self.filter_table)

        open_btn = QPushButton("Открыть")
        open_btn.clicked.connect(self.open_selected_level)
        new_btn = QPushButton("Новый")
        new_btn.clicked.connect(self.create_new_level)

        t = QWidget()
        l = QVBoxLayout(t)
        l.addWidget(self.search)
        l.addWidget(self.table)
        l.addWidget(open_btn)
        l.addWidget(new_btn)
        self.tabs.addTab(t, "Уровни")

        self.fill_table()

    def fill_table(self, text=""):
        cur = self.con.cursor()
        if text:
            res = cur.execute(
                "SELECT id, name, width, height FROM levels WHERE name LIKE ? ORDER BY id",
                (f"%{text}%",)
            ).fetchall()
        else:
            res = cur.execute("SELECT id, name, width, height FROM levels ORDER BY id").fetchall()

        self.table.clear()
        self.table.setColumnCount(4)
        self.table.setRowCount(len(res))
        self.table.setHorizontalHeaderLabels(["ID", "Название", "Ширина", "Высота"])

        for i, row in enumerate(res):
            for j, val in enumerate(row):
                self.table.setItem(i, j, QTableWidgetItem(str(val)))

    def filter_table(self, text):
        self.fill_table(text)

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

    def create_new_level(self):
        name, ok = QInputDialog.getText(self, "Новый уровень", "Название:")
        if not ok or not name.strip(): return

        w, ok = QInputDialog.getInt(self, "Размер", "Ширина:", 20, 5, 60)
        if not ok: return

        h, ok = QInputDialog.getInt(self, "Размер", "Высота:", 15, 5, 40)
        if not ok: return

        cur = self.con.cursor()
        cur.execute("INSERT INTO levels (name, width, height) VALUES (?, ?, ?)", (name, w, h))
        self.con.commit()

        self.fill_table()
        QMessageBox.information(self, "Успех", f"Уровень '{name}' создан!")

    def open_selected_level(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Выберите уровень!")
            return

        level_id = int(self.table.item(row, 0).text())
        w = int(self.table.item(row, 2).text())
        h = int(self.table.item(row, 3).text())

        self.canvas.set_level(w, h)
        self.tabs.setCurrentWidget(self.editor)
        self.setWindowTitle(f"Картограф — Уровень #{level_id}")

if __name__ == "__main__":
    init_db()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
