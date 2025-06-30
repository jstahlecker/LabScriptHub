#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QMainWindow,
    QCheckBox,
)  

from itc_final_figure import plot_itc, apply_seaborn_style


# ──────────────────────────────────────────────────────────────────────────────
# Custom list widget to support drag‑and‑drop
# ──────────────────────────────────────────────────────────────────────────────


class FileListWidget(QListWidget):
    """A `QListWidget` that accepts CSV files via drag & drop."""

    def __init__(self, parent: QMainWindow) -> None:  # noqa: D401 (imperative mood preferred)
        super().__init__(parent)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setAcceptDrops(True)

    # --- drag‑and‑drop events -------------------------------------------------
    def dragEnterEvent(self, event):  # noqa: N802 (Qt naming conventions)
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):  # noqa: N802
        self.dragEnterEvent(event)

    def dropEvent(self, event):  # noqa: N802
        window: "MainWindow" = self.window()  # type: ignore[name‑defined]
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.suffix.lower() == ".csv":
                    window._add_file(path)
        event.acceptProposedAction()


# ──────────────────────────────────────────────────────────────────────────────
# Main window
# ──────────────────────────────────────────────────────────────────────────────


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ITC Final Figure Generator")
        self.resize(720, 480)

        self.file_paths: list[Path] = []
        self.output_dir: Path | None = None

        # ---------- layout ----------
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # 1) file list + buttons
        file_row = QHBoxLayout()
        self.file_list = FileListWidget(self)
        file_row.addWidget(self.file_list, 3)

        btn_col = QVBoxLayout()
        browse_btn = QPushButton("Add CSV …")
        browse_btn.clicked.connect(self._browse_files)
        btn_col.addWidget(browse_btn)

        remove_btn = QPushButton("Remove selected")
        remove_btn.clicked.connect(self._remove_selected)
        btn_col.addWidget(remove_btn)
        btn_col.addStretch()
        file_row.addLayout(btn_col)

        root.addLayout(file_row)

        # 2) options row
        opts_row = QHBoxLayout()
        self.sep_edit = self._labeled_edit("CSV Separator", ",", opts_row)
        self.dec_edit = self._labeled_edit("Decimal Symbol", ".", opts_row)
        self.energy_edit = self._labeled_edit("Energy Unit", "kcal / mol", opts_row)
        root.addLayout(opts_row)
        # Seaborn style option
        style_row = QHBoxLayout()
        self.seaborn_cb = QCheckBox("Use seaborn style")
        style_row.addWidget(self.seaborn_cb)
        root.addLayout(style_row)

        # 3) output folder picker
        out_row = QHBoxLayout()
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("[same folder as CSV]")
        out_row.addWidget(QLabel("Output Folder:"))
        out_row.addWidget(self.out_edit, 1)
        out_browse = QPushButton("Browse …")
        out_browse.clicked.connect(self._browse_output_dir)
        out_row.addWidget(out_browse)
        root.addLayout(out_row)

        # 4) run button
        run_btn = QPushButton("Generate Figure")
        run_btn.setDefault(True)
        run_btn.clicked.connect(self._generate)
        root.addWidget(run_btn, alignment=Qt.AlignRight)

    # ---------- tiny helpers ----------
    @staticmethod
    def _labeled_edit(label: str, default: str, parent: QHBoxLayout) -> QLineEdit:
        box = QVBoxLayout()
        box.addWidget(QLabel(label))
        edit = QLineEdit(default)
        box.addWidget(edit)
        parent.addLayout(box)
        return edit

    # ---------- slots ----------
    def _browse_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select CSV files",
            "",
            "CSV Files (*.csv)",
        )
        for f in files:
            self._add_file(Path(f))

    def _add_file(self, path: Path) -> None:
        if path not in self.file_paths:
            self.file_paths.append(path)
            self.file_list.addItem(QListWidgetItem(path.name))

    def _remove_selected(self) -> None:
        for item in self.file_list.selectedItems():
            idx = self.file_list.row(item)
            self.file_list.takeItem(idx)
            del self.file_paths[idx]

    def _browse_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select output folder")
        if directory:
            self.output_dir = Path(directory)
            self.out_edit.setText(str(self.output_dir))

    def _generate(self) -> None:
        if not self.file_paths:
            QMessageBox.warning(self, "No files", "Add at least one CSV file first.")
            return

        sep = self.sep_edit.text() or ","
        dec = self.dec_edit.text() or "."
        energy = self.energy_edit.text() or "kcal / mol"
        out_folder = self.output_dir if self.output_dir else None
        use_seaborn = self.seaborn_cb.isChecked()

        if use_seaborn:
            apply_seaborn_style({"style": "ticks", "context": "paper"})

        try:
            for fp in list(self.file_paths):  # clone list because we may mutate it
                df = pd.read_csv(fp, sep=sep, decimal=dec)
                out_path = (out_folder or fp.parent) / f"{fp.stem}.png"
                plot_itc(df, out_path, energy_unit=energy)
            QMessageBox.information(self, "Done", "Figures generated successfully.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        finally:
            # Always clear UI list
            self.file_list.clear()
            self.file_paths.clear()


# ──────────────────────────────────────────────────────────────────────────────
# Optional dark theme helper
# ──────────────────────────────────────────────────────────────────────────────

def _apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(35, 35, 35))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)


# ──────────────────────────────────────────────────────────────────────────────
# Entry‑point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    _apply_dark_theme(app)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
