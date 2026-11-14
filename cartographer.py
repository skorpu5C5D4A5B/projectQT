import sys
import sqlite3
from collections import deque
from PyQt6.QtGui import QPainter, QColor, QPen, QPixmap, QAction, QFont
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QTabWidget, QLineEdit, QPushButton,
    QLabel, QMessageBox, QInputDialog, QFileDialog
)

DB = "cartographer.sqlite"
CELL_SIZE = 28


def init_db():
    connection = sqlite3.connect(DB)
    cursor = connection.cursor()
    cursor.executescript("""
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
    connection.commit()
    connection.close()


class Canvas(QWidget):
    def __init__(self, connection):
        super().__init__()
        self.connection = connection
        self.level_id = None
        self.width = 20
        self.height = 15
        self.tool = "wall"
        self.tiles = {}
        self.path = []

        self.setMinimumSize(self.width * CELL_SIZE + 2, self.height * CELL_SIZE + 2)

        self.pixmaps = {}
        colors = {"wall": "#555", "start": "#2ecc71", "finish": "#f1c40f", "enemy": "#e74c3c"}
        for kind, color in colors.items():
            pixmap = QPixmap(CELL_SIZE - 2, CELL_SIZE - 2)
            pixmap.fill(QColor(color))
            self.pixmaps[kind] = pixmap

    def set_level(self, level_id, width, height):
        self.level_id = level_id
        self.width = width
        self.height = height
        self.path = []
        self.setMinimumSize(self.width * CELL_SIZE + 2, self.height * CELL_SIZE + 2)
        self.load_tiles()

    def load_tiles(self):
        self.tiles = {}
        if self.level_id:
            cursor = self.connection.cursor()
            result = cursor.execute(
                "SELECT x, y, kind FROM tiles WHERE level_id = ?", (self.level_id,)
            ).fetchall()
            for x, y, kind in result:
                self.tiles[(x, y)] = kind
        self.update()

    def set_tool(self, tool):
        self.tool = tool

    def mousePressEvent(self, event):
        if not self.level_id:
            return

        x = int(event.position().x() // CELL_SIZE)
        y = int(event.position().y() // CELL_SIZE)

        if not (0 <= x < self.width and 0 <= y < self.height):
            return

        cursor = self.connection.cursor()
        key = (x, y)

        if self.tool == "erase":
            if key in self.tiles:
                del self.tiles[key]
                cursor.execute(
                    "DELETE FROM tiles WHERE level_id = ? AND x = ? AND y = ?",
                    (self.level_id, x, y)
                )
        else:
            if self.tool in ("start", "finish"):
                for old_key, old_value in list(self.tiles.items()):
                    if old_value == self.tool:
                        del self.tiles[old_key]
                        cursor.execute(
                            "DELETE FROM tiles WHERE level_id = ? AND x = ? AND y = ?",
                            (self.level_id, old_key[0], old_key[1])
                        )

            self.tiles[key] = self.tool
            cursor.execute(
                "INSERT OR REPLACE INTO tiles (level_id, x, y, kind) VALUES (?, ?, ?, ?)",
                (self.level_id, x, y, self.tool)
            )

        self.connection.commit()
        self.path = []
        self.update()

    def paintEvent(self, event):
        painter = QPainter()
        painter.begin(self)

        painter.fillRect(self.rect(), QColor("#fafafa"))

        painter.setPen(QPen(QColor("#ddd"), 1))
        for x in range(self.width + 1):
            painter.drawLine(x * CELL_SIZE, 0, x * CELL_SIZE, self.height * CELL_SIZE)
        for y in range(self.height + 1):
            painter.drawLine(0, y * CELL_SIZE, self.width * CELL_SIZE, y * CELL_SIZE)

        for (x, y), kind in self.tiles.items():
            painter.drawPixmap(x * CELL_SIZE + 1, y * CELL_SIZE + 1, self.pixmaps[kind])

        if self.path:
            painter.setPen(QPen(QColor("#3498db"), 3))
            for index in range(len(self.path) - 1):
                x1, y1 = self.path[index]
                x2, y2 = self.path[index + 1]
                painter.drawLine(
                    x1 * CELL_SIZE + CELL_SIZE // 2, y1 * CELL_SIZE + CELL_SIZE // 2,
                    x2 * CELL_SIZE + CELL_SIZE // 2, y2 * CELL_SIZE + CELL_SIZE // 2
                )

        painter.setPen(QColor("#333"))
        painter.setFont(QFont("Arial", 9))
        painter.drawText(6, 16, f"Инструмент: {self.tool}   Уровень #{self.level_id}")

        painter.end()

    def find_path(self):
        start = next((key for key, value in self.tiles.items() if value == "start"), None)
        finish = next((key for key, value in self.tiles.items() if value == "finish"), None)

        if not start or not finish:
            QMessageBox.warning(self, "Внимание", "Нужны старт и финиш!")
            return

        walls = {key for key, value in self.tiles.items() if value == "wall"}
        queue = deque([start])
        previous = {start: None}

        while queue:
            current = queue.popleft()
            if current == finish:
                break
            x, y = current
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                neighbor = (x + dx, y + dy)
                if (0 <= neighbor[0] < self.width and 0 <= neighbor[1] < self.height
                        and neighbor not in walls and neighbor not in previous):
                    previous[neighbor] = current
                    queue.append(neighbor)

        if finish not in previous:
            QMessageBox.information(self, "Поиск пути", "Путь не найден")
            self.path = []
            self.update()
            return

        path = []
        current = finish
        while current is not None:
            path.append(current)
            current = previous[current]

        self.path = path[::-1]
        self.update()


class StartWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Картограф")
        self.resize(450, 300)

        layout = QVBoxLayout(self)

        title = QLabel("Картограф")
        title.setStyleSheet("font-size: 28px; font-weight: bold;")

        description = QLabel(
            "Редактор лабиринтов с базой данных.\n"
            "Создавайте уровни, расставляйте стены\n"
            "и находите путь от старта до финиша."
        )
        description.setStyleSheet("font-size: 12px; color: #555;")

        button = QPushButton("Начать")
        button.setFixedWidth(150)
        button.setStyleSheet("""
            QPushButton {
                border: 1px solid #888;
                color: black;
                border-radius: 8px;
                padding: 10px;
                font-weight: bold;
            }
        """)
        button.clicked.connect(self.go)

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(20)
        layout.addWidget(button)
        layout.addStretch()

    def go(self):
        self.window = MainWindow()
        self.window.show()
        self.close()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Картограф")
        self.resize(1100, 700)
        self.showMaximized()

        self.connection = sqlite3.connect(DB)

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
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("Файл")

        export_action = QAction("Экспорт в PNG", self)
        export_action.triggered.connect(self.export_png)
        file_menu.addAction(export_action)

        file_menu.addSeparator()
        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def build_levels(self):
        self.table = QTableWidget()
        self.table.setSortingEnabled(True)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск...")
        self.search.textChanged.connect(self.filter_table)

        open_button = QPushButton("Открыть")
        open_button.clicked.connect(self.open_selected_level)
        new_button = QPushButton("Новый")
        new_button.clicked.connect(self.create_new_level)

        levels_widget = QWidget()
        levels_layout = QVBoxLayout(levels_widget)
        levels_layout.addWidget(self.search)
        levels_layout.addWidget(self.table)
        levels_layout.addWidget(open_button)
        levels_layout.addWidget(new_button)
        self.tabs.addTab(levels_widget, "Уровни")

        self.fill_table()

    def fill_table(self, text=""):
        cursor = self.connection.cursor()
        if text:
            result = cursor.execute(
                "SELECT id, name, width, height FROM levels WHERE name LIKE ? ORDER BY id",
                (f"%{text}%",)
            ).fetchall()
        else:
            result = cursor.execute(
                "SELECT id, name, width, height FROM levels ORDER BY id"
            ).fetchall()

        self.table.clear()
        self.table.setColumnCount(4)
        self.table.setRowCount(len(result))
        self.table.setHorizontalHeaderLabels(["ID", "Название", "Ширина", "Высота"])

        for row_index, row in enumerate(result):
            for column_index, value in enumerate(row):
                self.table.setItem(
                    row_index, column_index, QTableWidgetItem(str(value))
                )

    def filter_table(self, text):
        self.fill_table(text)

    def build_editor(self):
        self.editor = QWidget()
        editor_layout = QHBoxLayout(self.editor)

        tools_layout = QVBoxLayout()
        tools_layout.addWidget(QLabel("Инструменты:"))

        wall_button = QPushButton("🧱 Стена")
        wall_button.clicked.connect(lambda: self.canvas.set_tool("wall"))
        tools_layout.addWidget(wall_button)

        start_button = QPushButton("🟢 Старт")
        start_button.clicked.connect(lambda: self.canvas.set_tool("start"))
        tools_layout.addWidget(start_button)

        finish_button = QPushButton("🟡 Финиш")
        finish_button.clicked.connect(lambda: self.canvas.set_tool("finish"))
        tools_layout.addWidget(finish_button)

        enemy_button = QPushButton("👾 Враг")
        enemy_button.clicked.connect(lambda: self.canvas.set_tool("enemy"))
        tools_layout.addWidget(enemy_button)

        erase_button = QPushButton("🧽 Ластик")
        erase_button.clicked.connect(lambda: self.canvas.set_tool("erase"))
        tools_layout.addWidget(erase_button)

        tools_layout.addStretch()

        path_button = QPushButton("🔎 Найти путь")
        path_button.clicked.connect(lambda: self.canvas.find_path())
        tools_layout.addWidget(path_button)

        stats_button = QPushButton("📊 Статистика")
        stats_button.clicked.connect(self.show_stats)
        tools_layout.addWidget(stats_button)

        self.canvas = Canvas(self.connection)

        editor_layout.addLayout(tools_layout)
        editor_layout.addWidget(self.canvas, 1)
        self.tabs.addTab(self.editor, "Редактор")

    def create_new_level(self):
        name, ok = QInputDialog.getText(self, "Новый уровень", "Название:")
        if not ok or not name.strip():
            return

        width, ok = QInputDialog.getInt(self, "Размер", "Ширина:", 20, 5, 60)
        if not ok:
            return

        height, ok = QInputDialog.getInt(self, "Размер", "Высота:", 15, 5, 40)
        if not ok:
            return

        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT INTO levels (name, width, height) VALUES (?, ?, ?)",
            (name, width, height)
        )
        self.connection.commit()

        self.fill_table()
        QMessageBox.information(self, "Успех", f"Уровень '{name}' создан!")

    def open_selected_level(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Выберите уровень!")
            return

        level_id = int(self.table.item(row, 0).text())
        width = int(self.table.item(row, 2).text())
        height = int(self.table.item(row, 3).text())

        self.canvas.set_level(level_id, width, height)
        self.tabs.setCurrentWidget(self.editor)
        self.setWindowTitle(f"Картограф — Уровень #{level_id}")

    def export_png(self):
        if not self.canvas.level_id:
            QMessageBox.warning(self, "Ошибка", "Сначала откройте уровень!")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт PNG", "map.png", "PNG (*.png)"
        )
        if path:
            pixmap = QPixmap(self.canvas.size())
            self.canvas.render(pixmap)
            pixmap.save(path)
            QMessageBox.information(self, "Успех", "Карта сохранена!")

    def show_stats(self):
        if not self.canvas.level_id:
            QMessageBox.warning(self, "Ошибка", "Сначала откройте уровень!")
            return

        cursor = self.connection.cursor()
        result = cursor.execute("""
            SELECT kind, COUNT(*) FROM tiles
            WHERE level_id = ? GROUP BY kind
        """, (self.canvas.level_id,)).fetchall()

        if not result:
            QMessageBox.information(self, "Статистика", "На уровне пока нет объектов.")
            return

        text = f"Уровень #{self.canvas.level_id}:\n\n"
        for kind, count in result:
            text += f"{kind}: {count}\n"

        QMessageBox.information(self, "Статистика", text)


if __name__ == "__main__":
    init_db()
    application = QApplication(sys.argv)
    start_window = StartWindow()
    start_window.show()
    sys.exit(application.exec())
