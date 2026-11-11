import sys
import sqlite3
from collections import deque
from PyQt6.QtGui import QPainter, QColor, QPen, QPixmap, QAction, QFont
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QTabWidget, QLineEdit, QPushButton,
    QLabel, QMessageBox, QInputDialog, QFileDialog
)

# посмотреть ошибки, дизайн, exe и презетавция

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
    def __init__(self, con):
        super().__init__()
        self.con = con
        self.level_id = None
        self.w = 20
        self.h = 15
        self.tool = "wall"
        self.tiles = {}
        self.path = []

        self.setMinimumSize(self.w * C + 2, self.h * C + 2)

        self.px = {}
        colors = {"wall": "#555", "start": "#2ecc71", "finish": "#f1c40f", "enemy": "#e74c3c"}
        for k, c in colors.items():
            p = QPixmap(C - 2, C - 2)
            p.fill(QColor(c))
            self.px[k] = p

    def set_level(self, level_id, w, h):
        self.level_id = level_id
        self.w = w
        self.h = h
        self.path = []
        self.setMinimumSize(self.w * C + 2, self.h * C + 2)
        self.load_tiles()

    def load_tiles(self):
        self.tiles = {}
        if self.level_id:
            cur = self.con.cursor()
            res = cur.execute("SELECT x, y, kind FROM tiles WHERE level_id = ?", (self.level_id,)).fetchall()
            for x, y, k in res:
                self.tiles[(x, y)] = k
        self.update()

    def set_tool(self, tool):
        self.tool = tool

    def mousePressEvent(self, event):
        if not self.level_id:
            return

        x = int(event.position().x() // C)
        y = int(event.position().y() // C)

        if not (0 <= x < self.w and 0 <= y < self.h):
            return

        cur = self.con.cursor()
        k = (x, y)

        if self.tool == "erase":
            if k in self.tiles:
                del self.tiles[k]
                cur.execute("DELETE FROM tiles WHERE level_id = ? AND x = ? AND y = ?", (self.level_id, x, y))
        else:
            if self.tool in ("start", "finish"):
                for i, v in list(self.tiles.items()):
                    if v == self.tool:
                        del self.tiles[i]
                        cur.execute("DELETE FROM tiles WHERE level_id = ? AND x = ? AND y = ?",
                                    (self.level_id, i[0], i[1]))

            self.tiles[k] = self.tool
            cur.execute("INSERT OR REPLACE INTO tiles (level_id, x, y, kind) VALUES (?, ?, ?, ?)",
                        (self.level_id, x, y, self.tool))

        self.con.commit()
        self.path = []
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

        for (x, y), k in self.tiles.items():
            qp.drawPixmap(x * C + 1, y * C + 1, self.px[k])

        if self.path:
            qp.setPen(QPen(QColor("#3498db"), 3))
            for i in range(len(self.path) - 1):
                x1, y1 = self.path[i]
                x2, y2 = self.path[i + 1]
                qp.drawLine(x1 * C + C // 2, y1 * C + C // 2,
                            x2 * C + C // 2, y2 * C + C // 2)

        qp.setPen(QColor("#333"))
        qp.setFont(QFont("Arial", 9))
        qp.drawText(6, 16, f"Инструмент: {self.tool}   Уровень #{self.level_id}")

        qp.end()

    def find_path(self):
        start = next((k for k, v in self.tiles.items() if v == "start"), None)
        finish = next((k for k, v in self.tiles.items() if v == "finish"), None)

        if not start or not finish:
            QMessageBox.warning(self, "Внимание", "Нужны старт и финиш!")
            return

        walls = {k for k, v in self.tiles.items() if v == "wall"}
        q = deque([start])
        prev = {start: None}

        while q:
            cur = q.popleft()
            if cur == finish:
                break
            x, y = cur
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                nxt = (x + dx, y + dy)
                if (0 <= nxt[0] < self.w and 0 <= nxt[1] < self.h
                        and nxt not in walls and nxt not in prev):
                    prev[nxt] = cur
                    q.append(nxt)

        if finish not in prev:
            QMessageBox.information(self, "Поиск пути", "Путь не найден")
            self.path = []
            self.update()
            return

        path = []
        cur = finish
        while cur is not None:
            path.append(cur)
            cur = prev[cur]

        self.path = path[::-1]
        self.update()

class StartWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Картограф")
        self.resize(450, 300)

        l = QVBoxLayout(self)

        t = QLabel("Картограф")
        t.setStyleSheet("font-size: 28px; font-weight: bold;")

        d = QLabel("Редактор лабиринтов с базой данных.\nСоздавайте уровни, расставляйте стены\nи находите путь от старта до финиша.")
        d.setStyleSheet("font-size: 12px; color: #555;")

        b = QPushButton("Начать")
        b.setFixedWidth(150)
        b.setStyleSheet("""
            QPushButton {
                border: 1px solid #888;
                color: black;
                border-radius: 8px;
                padding: 10px;
                font-weight: bold;
            }
        """)
        b.clicked.connect(self.go)

        l.addStretch()
        l.addWidget(t)
        l.addWidget(d)
        l.addSpacing(20)
        l.addWidget(b)
        l.addStretch()

    def go(self):
        self.w = MainWindow()
        self.w.show()
        self.close()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Картограф")
        self.resize(1100, 700)

        self.con = sqlite3.connect(DB)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.build_levels()
        self.build_editor()
        self.build_menu()

        self.apply_style()

    def apply_style(self):
        self.setStyleSheet("""
            QPushButton {
                border: 1px solid #888;
                border-radius: 10px;
                padding: 6px;
                background-color: #f0f0f0;
            }""")

    def build_menu(self):
        m = self.menuBar()
        f = m.addMenu("Файл")

        a = QAction("Экспорт в PNG", self)
        a.triggered.connect(self.export_png)
        f.addAction(a)

        f.addSeparator()
        a = QAction("Выход", self)
        a.triggered.connect(self.close)
        f.addAction(a)

    def build_levels(self):
        self.table = QTableWidget()
        self.table.setSortingEnabled(True)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск...")
        self.search.textChanged.connect(self.filter_table)

        b1 = QPushButton("Открыть")
        b1.clicked.connect(self.open_selected_level)
        b2 = QPushButton("Новый")
        b2.clicked.connect(self.create_new_level)

        t = QWidget()
        l = QVBoxLayout(t)
        l.addWidget(self.search)
        l.addWidget(self.table)
        l.addWidget(b1)
        l.addWidget(b2)
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

        for i, r in enumerate(res):
            for j, v in enumerate(r):
                self.table.setItem(i, j, QTableWidgetItem(str(v)))

    def filter_table(self, text):
        self.fill_table(text)

    def build_editor(self):
        self.editor = QWidget()
        l = QHBoxLayout(self.editor)

        t = QVBoxLayout()
        t.addWidget(QLabel("Инструменты:"))

        b = QPushButton("🧱 Стена")
        b.clicked.connect(lambda: self.canvas.set_tool("wall"))
        t.addWidget(b)

        b = QPushButton("🟢 Старт")
        b.clicked.connect(lambda: self.canvas.set_tool("start"))
        t.addWidget(b)

        b = QPushButton("🟡 Финиш")
        b.clicked.connect(lambda: self.canvas.set_tool("finish"))
        t.addWidget(b)

        b = QPushButton("👾 Враг")
        b.clicked.connect(lambda: self.canvas.set_tool("enemy"))
        t.addWidget(b)

        b = QPushButton("🧽 Ластик")
        b.clicked.connect(lambda: self.canvas.set_tool("erase"))
        t.addWidget(b)

        t.addStretch()

        b = QPushButton("🔎 Найти путь")
        b.clicked.connect(lambda: self.canvas.find_path())
        t.addWidget(b)

        b = QPushButton("📊 Статистика")
        b.clicked.connect(self.show_stats)
        t.addWidget(b)

        self.canvas = Canvas(self.con)

        l.addLayout(t)
        l.addWidget(self.canvas, 1)
        self.tabs.addTab(self.editor, "Редактор")

    def create_new_level(self):
        n, ok = QInputDialog.getText(self, "Новый уровень", "Название:")
        if not ok or not n.strip(): return

        w, ok = QInputDialog.getInt(self, "Размер", "Ширина:", 20, 5, 60)
        if not ok: return

        h, ok = QInputDialog.getInt(self, "Размер", "Высота:", 15, 5, 40)
        if not ok: return

        cur = self.con.cursor()
        cur.execute("INSERT INTO levels (name, width, height) VALUES (?, ?, ?)", (n, w, h))
        self.con.commit()

        self.fill_table()
        QMessageBox.information(self, "Успех", f"Уровень '{n}' создан!")

    def open_selected_level(self):
        r = self.table.currentRow()
        if r < 0:
            QMessageBox.warning(self, "Внимание", "Выберите уровень!")
            return

        level_id = int(self.table.item(r, 0).text())
        w = int(self.table.item(r, 2).text())
        h = int(self.table.item(r, 3).text())

        self.canvas.set_level(level_id, w, h)
        self.tabs.setCurrentWidget(self.editor)
        self.setWindowTitle(f"Картограф — Уровень #{level_id}")

    def export_png(self):
        if not self.canvas.level_id:
            QMessageBox.warning(self, "Ошибка", "Сначала откройте уровень!")
            return

        p, _ = QFileDialog.getSaveFileName(self, "Экспорт PNG", "map.png", "PNG (*.png)")
        if p:
            pix = QPixmap(self.canvas.size())
            self.canvas.render(pix)
            pix.save(p)
            QMessageBox.information(self, "Успех", "Карта сохранена!")

    def show_stats(self):
        if not self.canvas.level_id:
            QMessageBox.warning(self, "Ошибка", "Сначала откройте уровень!")
            return

        cur = self.con.cursor()
        res = cur.execute("""
            SELECT kind, COUNT(*) FROM tiles
            WHERE level_id = ? GROUP BY kind
        """, (self.canvas.level_id,)).fetchall()

        if not res:
            QMessageBox.information(self, "Статистика", "На уровне пока нет объектов.")
            return

        text = f"Уровень #{self.canvas.level_id}:\n\n"
        for k, c in res:
            text += f"{k}: {c}\n"

        QMessageBox.information(self, "Статистика", text)


if __name__ == "__main__":
    init_db()
    app = QApplication(sys.argv)
    s = StartWindow()
    s.show()
    sys.exit(app.exec())
