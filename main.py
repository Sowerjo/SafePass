import sys, os, json, time
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLineEdit,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout,
    QPushButton, QHBoxLayout, QToolButton, QStyledItemDelegate,
    QStyleOptionViewItem, QTabWidget, QMenu, QInputDialog
)
from PyQt5.QtCore import Qt, QTimer, QEvent
from PyQt5.QtGui import QPainter, QPen, QLinearGradient, QColor, QFont
from crypto_utils import create_master, verify_master, encrypt_data, decrypt_data

CONFIG = 'config.json'
VAULT  = 'vault.dat'


class AddLoginDialog(QDialog):
    def __init__(self, parent=None, initial=None):
        super().__init__(parent)
        self.setWindowTitle("✏️ Editar Login" if initial else "➕ Cadastrar Login")
        self.setFixedSize(420, 300)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.conta     = QLineEdit()
        self.site      = QLineEdit()
        self.login     = QLineEdit()
        self.senha     = QLineEdit(); self.senha.setEchoMode(QLineEdit.Password)
        self.descricao = QLineEdit()
        form.addRow("Conta:",     self.conta)
        form.addRow("Site:",      self.site)
        form.addRow("Login:",     self.login)
        form.addRow("Senha:",     self.senha)
        form.addRow("Descrição:", self.descricao)
        layout.addLayout(form)

        if initial:
            self.conta.setText(initial[0])
            self.site.setText(initial[1])
            self.login.setText(initial[2])
            self.senha.setText(initial[3])
            self.descricao.setText(initial[4])

        btns = QHBoxLayout()
        btns.addStretch()
        ok     = QPushButton("OK");     ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancelar"); cancel.clicked.connect(self.reject)
        btns.addWidget(ok); btns.addWidget(cancel)
        layout.addLayout(btns)

    def data(self):
        return [
            self.conta.text().strip(),
            self.site.text().strip(),
            self.login.text().strip(),
            self.senha.text(),
            self.descricao.text().strip()
        ]


class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        # >>>>>> Adiciona ícone na janela <<<<<<
        self.setWindowIcon(QtGui.QIcon("icone.ico"))

        self.setWindowTitle("🔐 SafePass")
        self.setFixedSize(360, 220)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                          stop:0 #1abc9c, stop:1 #16a085);
                border-radius:10px;
            }
            QLabel#title {
                color:#fff; font-size:24px; font-weight:bold;
            }
            QLabel#prompt {
                color:#ddeeff; font-size:14px;
            }
            QLineEdit {
                padding:10px; border-radius:5px;
                border:1px solid #33ccff; background:#002233;
                color:#33ccff; font-size:14px;
            }
            QLineEdit:focus {
                border:1px solid #cc33ff;
            }
            QPushButton {
                background:#33ccff; color:#000;
                padding:10px 20px; border-radius:5px;
                font-size:14px; font-weight:bold;
            }
            QPushButton:hover {
                background:#cc33ff;
            }
        """)
        main = QVBoxLayout(self)
        main.setContentsMargins(20,20,20,20)
        main.setSpacing(15)
        title  = QtWidgets.QLabel("🔐 SafePass", objectName="title")
        prompt = QtWidgets.QLabel("Digite sua senha mestre", objectName="prompt")
        title.setAlignment(Qt.AlignCenter)
        prompt.setAlignment(Qt.AlignCenter)
        self.pw = QLineEdit(); self.pw.setEchoMode(QLineEdit.Password)
        self.pw.setPlaceholderText("Senha Mestre")
        self.pw.returnPressed.connect(self.accept)
        btn = QPushButton("Entrar"); btn.clicked.connect(self.accept)
        main.addStretch()
        main.addWidget(title)
        main.addWidget(prompt)
        main.addWidget(self.pw)
        main.addWidget(btn)
        main.addStretch()

    def get_password(self):
        return self.pw.text()


class MaskedDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        text = index.data() or ""
        masked = "*" * len(text)
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = masked
        style = QApplication.style() if not opt.widget else opt.widget.style()
        style.drawControl(QtWidgets.QStyle.CE_ItemViewItem, opt, painter, opt.widget)

    def createEditor(self, parent, option, index):
        e = QLineEdit(parent)
        e.setEchoMode(QLineEdit.Normal)
        return e

    def setEditorData(self, editor, index):
        editor.setText(index.data() or "")

    def setModelData(self, editor, model, index):
        model.setData(index, editor.text(), Qt.EditRole)


class TripleClickTable(QTableWidget):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._clicks = {}

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            idx = self.indexAt(ev.pos())
            if idx.isValid():
                r, c = idx.row(), idx.column()
                now = time.time()
                prev, pt = self._clicks.get((r, c), (0, 0))
                interval = QApplication.doubleClickInterval() / 1000.0
                cnt = prev + 1 if (now - pt) < interval else 1
                self._clicks[(r, c)] = (cnt, now)
                if cnt >= 3:
                    itm = self.item(r, c)
                    if itm:
                        self.editItem(itm)
                        QTimer.singleShot(0, self._focus_editor)
                    self._clicks[(r, c)] = (0, 0)
                    return
        super().mousePressEvent(ev)

    def _focus_editor(self):
        w = QApplication.focusWidget()
        if isinstance(w, QLineEdit):
            w.selectAll()
            w.setFocus()


class MainWindow(QMainWindow):
    def __init__(self, key):
        super().__init__()
        # >>>>>> Adiciona ícone na janela <<<<<<
        self.setWindowIcon(QtGui.QIcon("icone.ico"))

        self.key      = key
        self.pass_col = 3
        self.hovered  = (None, None, None)

        self.setWindowTitle("SafePass")
        self.resize(1000, 650)

        # central widget com borda neon
        ctr = QWidget(self)
        ctr.setObjectName("central")
        ctr.setStyleSheet("""
            QWidget#central {
                background-color: #000;
                margin: 6px;
            }
        """)
        self.setCentralWidget(ctr)

        layout = QVBoxLayout(ctr)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(8)

        # busca
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍  Search...")
        self.search.setFixedHeight(34)
        self.search.setStyleSheet("""
            QLineEdit {
                background-color: #002233;
                color: #33ccff;
                border: 1px solid #33ccff;
                border-radius: 4px;
                padding-left: 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #cc33ff;
            }
        """)
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)

        # abas
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                background: #002233; color: #33ccff;
                padding: 8px; margin-right: 2px;
                border-top-left-radius:4px; border-top-right-radius:4px;
            }
            QTabBar::tab:selected {
                background: #001121; color: #cc33ff;
            }
        """)
        layout.addWidget(self.tabs)

        # aba padrão
        default_tbl = self._create_futuristic_table()
        self.tabs.addTab(default_tbl, "Padrão")

        # botão de cópia
        self.copy_btn = QToolButton(default_tbl)
        self.copy_btn.setText("📋")
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.setStyleSheet("""
            QToolButton {
                background: #33ccff;
                border: none;
                border-radius: 8px;
                color: #000;
                font-size: 12px;
            }
        """)
        self.copy_btn.hide()

        # menu bar
        mb = self.menuBar()
        mb.setStyleSheet("background-color: #002233; color: #33ccff;")

        add_menu = mb.addMenu("➕ Add")
        add_menu.setStyleSheet("QMenu { background: #002233; color:#33ccff; }")
        add_menu.addAction("New Login", self.add_login)

        file_menu = mb.addMenu("💾 File")
        file_menu.setStyleSheet("QMenu { background: #002233; color:#33ccff; }")
        file_menu.addAction("Save Vault", self.save_vault)

        tabs_menu = mb.addMenu("📑 Tabs")
        tabs_menu.setStyleSheet("QMenu { background: #002233; color:#33ccff; }")
        tabs_menu.addAction("New Tab",       self.create_tab)
        tabs_menu.addAction("✏️ Rename Tab", self.rename_tab)
        tabs_menu.addAction("🗑️ Remove Tab", self.remove_tab)

        # carrega vault se existir (incluindo widths)
        if os.path.exists(VAULT):
            raw  = open(VAULT, 'rb').read()
            data = json.loads(decrypt_data(self.key, raw).decode())
            self.tabs.clear()
            for tab in data.get("tabs", []):
                tbl = self._create_futuristic_table()
                # popula linhas
                for row in tab["items"]:
                    self._populate_row(tbl, row)
                # reaplica larguras
                for c, w in enumerate(tab.get("widths", [])):
                    tbl.setColumnWidth(c, w)
                self.tabs.addTab(tbl, tab["name"])

    def _create_futuristic_table(self):
        table = TripleClickTable(0, 5)
        table.owner = self
        table.setHorizontalHeaderLabels(
            ["Account","Site","Login","Password","Description"]
        )
        table.setAlternatingRowColors(False)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        table.setShowGrid(True)
        table.setSortingEnabled(False)
        table.setEditTriggers(
            QtWidgets.QAbstractItemView.NoEditTriggers
        )
        table.setMouseTracking(True)
        table.cellEntered.connect(self._on_hover)
        table.viewport().installEventFilter(self)
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(
            lambda pos, tbl=table: self.on_table_context_menu(pos, tbl)
        )
        table.setItemDelegateForColumn(
            self.pass_col, MaskedDelegate(table)
        )
        table.setStyleSheet("""
            QTableWidget {
                background-color: rgba(0,0,0,200);
                gridline-color: #33ccff;
            }
            QHeaderView::section {
                background-color: #002233;
                color: #33ccff;
                border: 1px solid #33ccff;
                padding: 6px; font-weight: bold; font-size: 13px;
            }
            QTableWidget::item {
                background-color: transparent;
                color: #66d9ff; padding: 4px;
            }
            QTableWidget::item:selected {
                background-color: rgba(51,204,255,50);
                color: #fff;
            }
        """)
        return table

    def create_tab(self):
        name, ok = QInputDialog.getText(self, "Nova Aba", "Nome da aba:")
        if ok and name.strip():
            tbl = self._create_futuristic_table()
            self.tabs.addTab(tbl, name.strip())

    def rename_tab(self):
        idx = self.tabs.currentIndex()
        if idx < 0: return
        old = self.tabs.tabText(idx)
        name, ok = QInputDialog.getText(self, "Renomear Aba", "Novo nome:", text=old)
        if ok and name.strip():
            self.tabs.setTabText(idx, name.strip())

    def remove_tab(self):
        idx = self.tabs.currentIndex()
        if self.tabs.count() > 1 and idx >= 0:
            self.tabs.removeTab(idx)

    def add_login(self):
        tbl = self.tabs.currentWidget()
        dlg = AddLoginDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            self._populate_row(tbl, dlg.data())

    def _populate_row(self, table, row_data):
        r = table.rowCount()
        table.insertRow(r)
        for c, val in enumerate(row_data):
            itm = QTableWidgetItem(val)
            itm.setToolTip(val)
            itm.setFlags(itm.flags() | Qt.ItemIsEditable)
            table.setItem(r, c, itm)

    def on_table_context_menu(self, pos, table):
        row = table.rowAt(pos.y())
        if row < 0: return
        menu = QMenu()
        menu.addAction("✏️ Editar",  lambda: self.edit_cadastro(table, row))
        menu.addAction("🗑️ Excluir", lambda: table.removeRow(row))
        menu.exec_(table.viewport().mapToGlobal(pos))

    def edit_cadastro(self, table, row):
        data = [
            table.item(row,c).text() if table.item(row,c) else ''
            for c in range(table.columnCount())
        ]
        dlg = AddLoginDialog(self, initial=data)
        if dlg.exec_() == QDialog.Accepted:
            new = dlg.data()
            for c, val in enumerate(new):
                itm = table.item(row, c)
                if itm:
                    itm.setText(val)
                    itm.setToolTip(val)
                else:
                    itm = QTableWidgetItem(val)
                    itm.setFlags(itm.flags() | Qt.ItemIsEditable)
                    itm.setToolTip(val)
                    table.setItem(row, c, itm)

    def save_vault(self):
        payload = {"tabs": []}
        for i in range(self.tabs.count()):
            tbl  = self.tabs.widget(i)
            name = self.tabs.tabText(i)
            items = [
                [tbl.item(r,c).text() if tbl.item(r,c) else ''
                 for c in range(tbl.columnCount())]
                for r in range(tbl.rowCount())
            ]
            widths = [tbl.columnWidth(c) for c in range(tbl.columnCount())]
            payload["tabs"].append({
                "name": name,
                "items": items,
                "widths": widths
            })
        token = encrypt_data(self.key, json.dumps(payload).encode())
        with open(VAULT, 'wb') as f:
            f.write(token)
        QtWidgets.QMessageBox.information(self, "Sucesso", "Dados salvos e criptografados!")

    def _filter(self, txt):
        tbl = self.tabs.currentWidget()
        t = txt.lower()
        for r in range(tbl.rowCount()):
            ok = any(
                t in (tbl.item(r,c).text().lower() if tbl.item(r,c) else '')
                for c in range(tbl.columnCount())
            )
            tbl.setRowHidden(r, not ok)

    def _on_hover(self, r, c):
        tbl = self.tabs.currentWidget()
        itm = tbl.item(r, c)
        if not itm:
            self.copy_btn.hide()
            return
        rect = tbl.visualItemRect(itm)
        x, y = rect.right() - 22, rect.top() + 2
        self.copy_btn.setParent(tbl.viewport())
        self.copy_btn.setGeometry(x, y, 20, rect.height() - 4)
        self.copy_btn.show()
        try:
            self.copy_btn.clicked.disconnect()
        except:
            pass
        self.copy_btn.clicked.connect(lambda: self._copy(r, c))

    def _copy(self, r, c):
        tbl = self.tabs.currentWidget()
        text = tbl.item(r, c).text()
        QApplication.clipboard().setText(text)
        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), "Copiado!", tbl)

    def eventFilter(self, obj, ev):
        current = self.tabs.currentWidget()
        if isinstance(current, QTableWidget):
            if obj is current.viewport() and ev.type() == QEvent.Leave:
                self.copy_btn.hide()
        return super().eventFilter(obj, ev)

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect().adjusted(4, 4, -4, -4)
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0, QColor("#33ccff"))
        grad.setColorAt(1, QColor("#cc33ff"))
        pen = QPen(grad, 4)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, 8, 8)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Consolas", 11))

    if not os.path.exists(CONFIG):
        pw, ok = QtWidgets.QInputDialog.getText(
            None, "Primeira Execução",
            "Defina sua senha mestre:", QLineEdit.Password
        )
        if not ok or not pw:
            sys.exit()
        create_master(pw)

    dlg = LoginDialog()
    if dlg.exec_() != QDialog.Accepted:
        sys.exit()
    try:
        key = verify_master(dlg.get_password())
    except Exception as e:
        QtWidgets.QMessageBox.critical(None, "Erro", str(e))
        sys.exit()

    w = MainWindow(key)
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
