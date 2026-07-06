#!/usr/bin/env python3
import os
import re
import sys
import shutil
import tempfile
import traceback
import importlib.util
from pathlib import Path

# --- IMPORTANT: force a head-less backend BEFORE plot_run imports pyplot ----
import matplotlib
matplotlib.use("Agg")

import pandas as pd
import yaml

# --- make sure plot_run.py (next to this file) is importable -----------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import plot_run as core
except Exception as exc:  # pragma: no cover - import diagnostics
    raise ImportError(
        "Could not import plot_run.py. Place gui.py in the same folder as "
        f"plot_run.py. Original error: {exc}"
    )

from PySide6.QtCore import Qt, QTimer, QThread, QObject, Signal, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLabel, QPushButton, QListWidget, QListWidgetItem,
    QAbstractItemView, QFileDialog, QGroupBox, QCheckBox, QLineEdit, QComboBox,
    QDoubleSpinBox, QScrollArea, QSplitter, QMessageBox, QFrame, QSizePolicy,
)

SEABORN_AVAILABLE = importlib.util.find_spec("seaborn") is not None


# =============================================================================
#  File inspection helpers (reuse plot_run's reading conventions)
# =============================================================================
def read_header(fn):
    """Return the list of column-name cells from the 2nd line of the file,
    using the same UTF-16/tab -> UTF-8/comma fallback as plot_run.get_columns."""
    try:
        with open(fn, "r", encoding="utf-16") as f:
            f.readline()                       # skip 1st line
            return f.readline().strip().split("\t")
    except UnicodeDecodeError:
        with open(fn, "r", encoding="utf-8") as f:
            f.readline()
            return f.readline().strip().split(",")


def read_dataframe(fn):
    """Same read as plot_run.plot_run (header on the 3rd line, positional)."""
    try:
        return pd.read_csv(fn, header=2, delimiter="\t", encoding="UTF-16")
    except UnicodeDecodeError:
        return pd.read_csv(fn, header=2, delimiter=",", encoding="UTF-8")


def detect_types(header):
    """Work out which plot_run-compatible TYPE strings are available.

    - Any cell containing 'UV' + a 3-digit number -> 'UV_<nm>'
    - A bare 'UV' cell with no wavelength         -> 'UV'
    - Exact 'Cond' / 'Conc B' cells               -> those strings
    UV entries are returned first (they live on the left axis).
    """
    types, seen = [], set()
    uv_found = False
    for cell in header:
        c = cell.strip()
        if "UV" in c:
            uv_found = True
            for nm in re.findall(r"(\d{3})", c):
                t = f"UV_{nm}"
                if t not in seen:
                    seen.add(t)
                    types.append(t)
        for known in ("Conc B", "Cond"):
            if c == known and known not in seen:
                seen.add(known)
                types.append(known)
    if uv_found and not any(t.startswith("UV") for t in types):
        types.insert(0, "UV")
    uv = [t for t in types if t.startswith("UV")]
    other = [t for t in types if not t.startswith("UV")]
    return uv + other


def header_has_fraction(header):
    return any(c.strip() == "Fraction" for c in header)


def get_fraction_names(fn):
    """Return the list of fraction identifiers (native python values)."""
    try:
        df = read_dataframe(fn)
        idx = core.get_columns(fn, "Fraction")
        raw = df.iloc[:, idx + 1].dropna().values
        out = []
        for v in raw:
            out.append(v.item() if hasattr(v, "item") else v)
        return out
    except Exception:
        return []


def parse_opt_float(text):
    """'' -> None, otherwise float() or None on failure."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


# =============================================================================
#  Headless render entry point (runs in a worker thread; pure, no Qt)
# =============================================================================
def do_render(payload):
    """Translate a payload dict into plot_run's expected structures and call it."""
    # styling
    if payload["seaborn"] and SEABORN_AVAILABLE:
        core.apply_seaborn_style(payload["seaborn_params"])
    else:
        defaults = {k: v for k, v in core.mpl.rcParamsDefault.items()
                    if k != "backend"}
        core.mpl.rcParams.update(defaults)

    input_list = []
    for f in payload["files"]:
        if not f["types"]:
            continue
        input_list.append((
            Path(f["path"]),
            list(f["types"]),
            f["fraction_groups"] or None,
            f["color"] or None,
            f["uv_offset"],            # float or None
            f["scaling_factor"],       # float
            f["legend_label"] or None,
        ))

    global_params = {
        "show_fractions": payload["show_fractions"],
        "x_start": payload["x_start"],
        "x_end": payload["x_end"],
        "output_name": payload["output_name"],
        "y_offset_UV": payload["y_offset_uv"],
        "y_min_uv": payload["y_min_uv"],
        "y_max_uv": payload["y_max_uv"],
        "fig_size": tuple(payload["fig_size"]),
    }

    core.plt.close("all")
    core.plot_run(input_list, global_params)
    core.plt.close("all")
    return payload["output_name"]


class RenderWorker(QObject):
    done = Signal(str)
    error = Signal(str)

    @Slot(dict)
    def render(self, payload):
        try:
            path = do_render(payload)
            self.done.emit(str(path))
        except Exception as e:
            self.error.emit(f"{e}\n{traceback.format_exc()}")


# =============================================================================
#  Page 1 — file selection (browse + drag & drop + remove)
# =============================================================================
class FileListWidget(QListWidget):
    files_changed = Signal()

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setStyleSheet(
            "QListWidget{border:2px dashed #9aa4b2; border-radius:8px; padding:8px;}"
        )

    # drag & drop ------------------------------------------------------------
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            added = False
            for url in e.mimeData().urls():
                p = url.toLocalFile()
                if p and os.path.isfile(p):
                    self.add_path(p)
                    added = True
            e.acceptProposedAction()
            if added:
                self.files_changed.emit()
        else:
            super().dropEvent(e)

    # helpers ----------------------------------------------------------------
    def add_path(self, p):
        for i in range(self.count()):
            if self.item(i).data(Qt.UserRole) == p:
                return  # no duplicates
        item = QListWidgetItem(os.path.basename(p))
        item.setData(Qt.UserRole, p)
        item.setToolTip(p)
        self.addItem(item)

    def paths(self):
        return [self.item(i).data(Qt.UserRole) for i in range(self.count())]

    def remove_selected(self):
        for it in self.selectedItems():
            self.takeItem(self.row(it))
        self.files_changed.emit()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.remove_selected()
        else:
            super().keyPressEvent(e)


class FilePage(QWidget):
    plot_requested = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("ÄKTA Run Plotter")
        title.setStyleSheet("font-size:22px; font-weight:600;")
        subtitle = QLabel("Add one or more exported run files, then press Plot.")
        subtitle.setStyleSheet("color:#667; font-size:13px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        hint = QLabel("Drag & drop files below, or use Browse. "
                      "Select an entry and press Delete to remove it.")
        hint.setStyleSheet("color:#778; font-size:12px;")
        layout.addWidget(hint)

        self.list = FileListWidget()
        layout.addWidget(self.list, stretch=1)

        btn_row = QHBoxLayout()
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        remove = QPushButton("Remove selected")
        remove.clicked.connect(self.list.remove_selected)
        clear = QPushButton("Clear all")
        clear.clicked.connect(self._clear)
        btn_row.addWidget(browse)
        btn_row.addWidget(remove)
        btn_row.addWidget(clear)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.plot_btn = QPushButton("Plot  ▶")
        self.plot_btn.setMinimumHeight(40)
        self.plot_btn.setStyleSheet(
            "QPushButton{background:#2d6cdf; color:white; font-size:15px;"
            "font-weight:600; border:none; border-radius:8px;}"
            "QPushButton:hover{background:#255bbd;}"
        )
        self.plot_btn.clicked.connect(self._plot)
        layout.addWidget(self.plot_btn)

    def _browse(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select run files", "",
            "Data files (*.txt *.asc *.csv *.tsv *.dat);;All files (*)",
        )
        for f in files:
            self.list.add_path(f)
        if files:
            self.list.files_changed.emit()

    def _clear(self):
        self.list.clear()
        self.list.files_changed.emit()

    def _plot(self):
        if not self.list.paths():
            QMessageBox.warning(self, "No files", "Please add at least one file.")
            return
        self.plot_requested.emit()


# =============================================================================
#  Right-hand controls
# =============================================================================
class GlobalControls(QGroupBox):
    changed = Signal()

    def __init__(self):
        super().__init__("Global settings")
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignRight)

        self.show_fractions = QCheckBox("Show fraction ticks & labels")
        form.addRow(self.show_fractions)

        self.x_start = QLineEdit(); self.x_start.setPlaceholderText("(auto)")
        self.x_end = QLineEdit(); self.x_end.setPlaceholderText("(auto)")
        form.addRow("X start [mL]", self.x_start)
        form.addRow("X end [mL]", self.x_end)

        self.y_offset = QDoubleSpinBox()
        self.y_offset.setRange(-1e9, 1e9); self.y_offset.setDecimals(3)
        self.y_offset.setValue(0.0)
        form.addRow("UV y-offset (global)", self.y_offset)

        self.y_min = QLineEdit(); self.y_min.setPlaceholderText("(auto)")
        self.y_max = QLineEdit(); self.y_max.setPlaceholderText("(auto)")
        form.addRow("UV y-min", self.y_min)
        form.addRow("UV y-max", self.y_max)

        size_row = QHBoxLayout()
        self.fig_w = QDoubleSpinBox(); self.fig_w.setRange(1, 100)
        self.fig_w.setValue(10.0); self.fig_w.setDecimals(1); self.fig_w.setSingleStep(0.5)
        self.fig_h = QDoubleSpinBox(); self.fig_h.setRange(1, 100)
        self.fig_h.setValue(6.0); self.fig_h.setDecimals(1); self.fig_h.setSingleStep(0.5)
        size_row.addWidget(QLabel("W")); size_row.addWidget(self.fig_w)
        size_row.addWidget(QLabel("H")); size_row.addWidget(self.fig_h)
        wrap = QWidget(); wrap.setLayout(size_row)
        form.addRow("Figure size [in]", wrap)

        self.seaborn = QCheckBox("Use seaborn theme")
        self.seaborn.setEnabled(SEABORN_AVAILABLE)
        if not SEABORN_AVAILABLE:
            self.seaborn.setToolTip("seaborn is not installed")
        self.sb_style = QComboBox()
        self.sb_style.addItems(["ticks", "darkgrid", "whitegrid", "white", "dark"])
        self.sb_context = QComboBox()
        self.sb_context.addItems(["paper", "notebook", "talk", "poster"])
        self.sb_style.setEnabled(False)
        self.sb_context.setEnabled(False)
        self.seaborn.toggled.connect(self.sb_style.setEnabled)
        self.seaborn.toggled.connect(self.sb_context.setEnabled)
        form.addRow(self.seaborn)
        form.addRow("Seaborn style", self.sb_style)
        form.addRow("Seaborn context", self.sb_context)

        # propagate every change
        self.show_fractions.toggled.connect(self.changed)
        self.seaborn.toggled.connect(self.changed)
        for le in (self.x_start, self.x_end, self.y_min, self.y_max):
            le.editingFinished.connect(self.changed)
        for sp in (self.y_offset, self.fig_w, self.fig_h):
            sp.valueChanged.connect(lambda *_: self.changed.emit())
        for cb in (self.sb_style, self.sb_context):
            cb.currentIndexChanged.connect(lambda *_: self.changed.emit())

    def to_config(self):
        return {
            "show_fractions": self.show_fractions.isChecked(),
            "x_start": parse_opt_float(self.x_start.text()),
            "x_end": parse_opt_float(self.x_end.text()),
            "y_offset_uv": self.y_offset.value(),
            "y_min_uv": parse_opt_float(self.y_min.text()),
            "y_max_uv": parse_opt_float(self.y_max.text()),
            "fig_size": [self.fig_w.value(), self.fig_h.value()],
            "seaborn": self.seaborn.isChecked() and SEABORN_AVAILABLE,
            "seaborn_params": {
                "style": self.sb_style.currentText(),
                "context": self.sb_context.currentText(),
            },
        }


class FractionGroupRow(QWidget):
    """One shaded region: START / END / COLOR + remove."""
    changed = Signal()
    remove_requested = Signal(object)

    def __init__(self, fraction_names):
        super().__init__()
        self._names = fraction_names
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)

        self.start = QComboBox(); self.start.setEditable(True)
        self.end = QComboBox(); self.end.setEditable(True)
        for combo in (self.start, self.end):
            for v in fraction_names:
                combo.addItem(str(v), v)         # keep native value as data
        self.color = QLineEdit("tab:blue"); self.color.setMaximumWidth(90)
        rm = QPushButton("✕"); rm.setMaximumWidth(28)
        rm.setToolTip("Remove region")

        row.addWidget(QLabel("from")); row.addWidget(self.start, 1)
        row.addWidget(QLabel("to")); row.addWidget(self.end, 1)
        row.addWidget(QLabel("color")); row.addWidget(self.color)
        row.addStretch(0)
        row.addWidget(rm)

        self.start.currentIndexChanged.connect(lambda *_: self.changed.emit())
        self.start.editTextChanged.connect(lambda *_: self.changed.emit())
        self.end.currentIndexChanged.connect(lambda *_: self.changed.emit())
        self.end.editTextChanged.connect(lambda *_: self.changed.emit())
        self.color.editingFinished.connect(self.changed)
        rm.clicked.connect(lambda: self.remove_requested.emit(self))

    @staticmethod
    def _value(combo):
        data = combo.currentData()
        if data is not None and combo.currentText() == str(data):
            return data                          # picked from list -> native type
        return combo.currentText()               # typed something custom

    def to_config(self):
        return {
            "START": self._value(self.start),
            "END": self._value(self.end),
            "COLOR": self.color.text().strip() or "tab:blue",
        }


class FileControls(QGroupBox):
    changed = Signal()

    def __init__(self, path):
        super().__init__(os.path.basename(path))
        self.path = path
        self.setToolTip(path)
        header = read_header(path)
        self.available_types = detect_types(header)
        self.has_fraction = header_has_fraction(header)
        self.fraction_names = get_fraction_names(path) if self.has_fraction else []

        outer = QVBoxLayout(self)

        # --- plottable types (clickable toggles) ---------------------------
        outer.addWidget(self._section_label("Plot data (click to toggle)"))
        self.type_boxes = []
        if self.available_types:
            grid = QHBoxLayout(); grid.setSpacing(12)
            col = QVBoxLayout()
            for i, t in enumerate(self.available_types):
                cb = QCheckBox(self._pretty_type(t))
                cb.setProperty("type_str", t)
                self.type_boxes.append(cb)
                col.addWidget(cb)
                if (i + 1) % 4 == 0:
                    grid.addLayout(col); col = QVBoxLayout()
            grid.addLayout(col); grid.addStretch(1)
            wrap = QWidget(); wrap.setLayout(grid)
            outer.addWidget(wrap)
            # default: first UV on
            for cb in self.type_boxes:
                if cb.property("type_str").startswith("UV"):
                    cb.setChecked(True)
                    break
        else:
            lbl = QLabel("No plottable columns detected in this file.")
            lbl.setStyleSheet("color:#a55;")
            outer.addWidget(lbl)

        self.warn = QLabel("")
        self.warn.setStyleSheet("color:#b8860b; font-size:11px;")
        outer.addWidget(self.warn)

        # --- per-file appearance -------------------------------------------
        form = QFormLayout()
        self.color = QLineEdit(); self.color.setPlaceholderText("(default) e.g. tab:blue, #333, red")
        form.addRow("UV colour", self.color)

        self.uv_offset = QLineEdit(); self.uv_offset.setPlaceholderText("(use global)")
        form.addRow("UV y-offset", self.uv_offset)

        self.scaling = QDoubleSpinBox()
        self.scaling.setRange(0.0, 1e9); self.scaling.setDecimals(4)
        self.scaling.setValue(1.0); self.scaling.setSingleStep(0.1)
        form.addRow("UV scaling factor", self.scaling)

        self.legend = QLineEdit(); self.legend.setPlaceholderText("(auto) — overrides UV legend text")
        form.addRow("Legend label", self.legend)
        outer.addLayout(form)

        # --- fraction groups (shaded regions) ------------------------------
        if self.has_fraction:
            outer.addWidget(self._section_label("Shaded fraction regions"))
            self.frac_container = QVBoxLayout()
            self.frac_rows = []
            cw = QWidget(); cw.setLayout(self.frac_container)
            outer.addWidget(cw)
            add = QPushButton("+ Add region")
            add.clicked.connect(self._add_fraction_row)
            outer.addWidget(add, alignment=Qt.AlignLeft)
        else:
            self.frac_rows = []

        # --- wire up signals (after defaults are set) ----------------------
        for cb in self.type_boxes:
            cb.toggled.connect(self._on_change)
        self.color.editingFinished.connect(self.changed)
        self.uv_offset.editingFinished.connect(self.changed)
        self.scaling.valueChanged.connect(lambda *_: self.changed.emit())
        self.legend.editingFinished.connect(self.changed)

    # helpers ----------------------------------------------------------------
    @staticmethod
    def _section_label(text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight:600; margin-top:6px;")
        return lbl

    @staticmethod
    def _pretty_type(t):
        if t.startswith("UV_"):
            return f"UV {t.split('_', 1)[1]} nm"
        if t == "UV":
            return "UV"
        if t == "Conc B":
            return "Concentration B"
        if t == "Cond":
            return "Conductivity"
        return t

    def _on_change(self, *_):
        self._update_warning()
        self.changed.emit()

    def _update_warning(self):
        types = self.selected_types()
        non_uv = [t for t in types if "UV" not in t]
        has_uv = any("UV" in t for t in types)
        msgs = []
        if len(non_uv) > 2:
            msgs.append("plot_run expects at most 2 non-UV traces per file.")
        if types and not has_uv:
            msgs.append("No UV selected — fraction shading needs a UV trace.")
        self.warn.setText("  ".join(msgs))

    def _add_fraction_row(self):
        row = FractionGroupRow(self.fraction_names)
        row.changed.connect(self.changed)
        row.remove_requested.connect(self._remove_fraction_row)
        self.frac_rows.append(row)
        self.frac_container.addWidget(row)
        self.changed.emit()

    def _remove_fraction_row(self, row):
        if row in self.frac_rows:
            self.frac_rows.remove(row)
            row.setParent(None)
            row.deleteLater()
            self.changed.emit()

    def selected_types(self):
        return [cb.property("type_str") for cb in self.type_boxes if cb.isChecked()]

    def to_config(self):
        groups = [r.to_config() for r in self.frac_rows]
        return {
            "path": self.path,
            "types": self.selected_types(),
            "color": self.color.text().strip(),
            "uv_offset": parse_opt_float(self.uv_offset.text()),
            "scaling_factor": self.scaling.value(),
            "legend_label": self.legend.text().strip(),
            "fraction_groups": groups or None,
        }


# =============================================================================
#  The live preview canvas (a QLabel that rescales its pixmap)
# =============================================================================
class PlotCanvas(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(420, 320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("background:#ffffff; color:#99a; border:1px solid #ccc;")
        self.setText("Toggle data types on the right to build the plot.")
        self._pix = None

    def set_image(self, path):
        try:
            data = Path(path).read_bytes()            # bypass QPixmap file cache
        except Exception:
            self.setText("Preview unavailable.")
            return
        pix = QPixmap()
        if not pix.loadFromData(data):
            self.setText("Could not load preview image.")
            return
        self._pix = pix
        self._rescale()

    def _rescale(self):
        if self._pix is None:
            return
        self.setPixmap(self._pix.scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, e):
        self._rescale()
        super().resizeEvent(e)


# =============================================================================
#  Main window
# =============================================================================
class MainWindow(QMainWindow):
    render_requested = Signal(dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ÄKTA Run Plotter")
        self.resize(1180, 760)

        self._tmpdir = tempfile.mkdtemp(prefix="aktaplot_")
        self.preview_path = os.path.join(self._tmpdir, "preview.png")
        self._busy = False
        self._pending = None
        self._has_preview = False

        # --- pages ----------------------------------------------------------
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.filepage = FilePage()
        self.filepage.plot_requested.connect(self.show_plot_page)
        self.stack.addWidget(self.filepage)

        self.plotpage = self._build_plot_page()
        self.stack.addWidget(self.plotpage)

        # --- background render thread --------------------------------------
        self.thread = QThread()
        self.worker = RenderWorker()
        self.worker.moveToThread(self.thread)
        self.render_requested.connect(self.worker.render)
        self.worker.done.connect(self._on_render_done)
        self.worker.error.connect(self._on_render_error)
        self.thread.start()

        # --- debounce timer -------------------------------------------------
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._fire_render)

        self.file_controls = {}   # path -> FileControls (cached across pages)

    # ------------------------------------------------------------------ pages
    def _build_plot_page(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(10, 10, 10, 10)

        # top bar
        top = QHBoxLayout()
        back = QPushButton("◀ Back")
        back.clicked.connect(lambda: self.stack.setCurrentWidget(self.filepage))
        top.addWidget(back)
        top.addStretch(1)
        self.status = QLabel("Ready")
        self.status.setStyleSheet("color:#667;")
        top.addWidget(self.status)
        v.addLayout(top)

        # splitter: canvas | controls
        splitter = QSplitter(Qt.Horizontal)
        self.canvas = PlotCanvas()
        splitter.addWidget(self.canvas)

        # right column (scrollable)
        right = QWidget()
        rlay = QVBoxLayout(right)
        self.global_controls = GlobalControls()
        self.global_controls.changed.connect(self.schedule_update)
        rlay.addWidget(self.global_controls)

        self.files_holder = QWidget()
        self.files_layout = QVBoxLayout(self.files_holder)
        self.files_layout.setContentsMargins(0, 0, 0, 0)
        rlay.addWidget(self.files_holder)
        rlay.addStretch(1)

        # action buttons
        actions = QHBoxLayout()
        save = QPushButton("Save figure…")
        save.clicked.connect(self.save_figure)
        export = QPushButton("Export YAML…")
        export.clicked.connect(self.export_yaml)
        actions.addWidget(save)
        actions.addWidget(export)
        rlay.addLayout(actions)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(right)
        scroll.setMinimumWidth(380)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([700, 430])
        v.addWidget(splitter, stretch=1)
        return page

    def show_plot_page(self):
        self._rebuild_file_controls()
        self.stack.setCurrentWidget(self.plotpage)
        self.schedule_update()

    def _rebuild_file_controls(self):
        current = self.filepage.list.paths()

        # drop controls for removed files
        for path in list(self.file_controls):
            if path not in current:
                fc = self.file_controls.pop(path)
                fc.setParent(None)
                fc.deleteLater()

        # detach everything from the layout (keeps cached widgets alive)
        while self.files_layout.count():
            item = self.files_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        # (re)add in file-list order, creating new controls as needed
        for path in current:
            fc = self.file_controls.get(path)
            if fc is None:
                try:
                    fc = FileControls(path)
                except Exception as e:
                    QMessageBox.warning(
                        self, "File error",
                        f"Could not read '{os.path.basename(path)}':\n{e}")
                    continue
                fc.changed.connect(self.schedule_update)
                self.file_controls[path] = fc
            fc.setParent(self.files_holder)
            self.files_layout.addWidget(fc)
            fc.show()

    # --------------------------------------------------------------- rendering
    def schedule_update(self):
        self._timer.start()

    def build_payload(self, output_path):
        g = self.global_controls.to_config()
        files = [self.file_controls[p].to_config()
                 for p in self.filepage.list.paths()
                 if p in self.file_controls]
        payload = dict(g)
        payload["files"] = files
        payload["output_name"] = str(output_path)
        return payload

    def _fire_render(self):
        payload = self.build_payload(self.preview_path)
        if self._busy:
            self._pending = payload
            return
        self._busy = True
        self.status.setText("Updating…")
        self.render_requested.emit(payload)

    def _drain_pending(self):
        if self._pending is not None:
            p, self._pending = self._pending, None
            self._busy = True
            self.status.setText("Updating…")
            self.render_requested.emit(p)

    def _on_render_done(self, path):
        self._busy = False
        self._has_preview = True
        self.canvas.set_image(path)
        self.status.setText("Ready")
        self._drain_pending()

    def _on_render_error(self, msg):
        self._busy = False
        first = msg.splitlines()[0] if msg else "render failed"
        self.status.setText(f"⚠ {first}")
        self.canvas.setText(f"Could not render:\n{first}")
        self._drain_pending()

    # ------------------------------------------------------------------ export
    def save_figure(self):
        if not self._has_preview or not os.path.exists(self.preview_path):
            QMessageBox.information(
                self, "Nothing to save",
                "Build a plot first (select at least one data type).")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save figure", "plot.png", "PNG image (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        try:
            # the preview is already rendered at 600 dpi by plot_run — just copy
            shutil.copyfile(self.preview_path, path)
            self.status.setText(f"Saved → {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))

    def export_yaml(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export YAML config", "input.yaml", "YAML (*.yaml *.yml)")
        if not path:
            return
        g = self.global_controls.to_config()
        cfg = {"USE_SEABORN": g["seaborn"]}
        if g["seaborn"]:
            cfg["SEABORN_PARAMS"] = g["seaborn_params"]
        cfg["SHOW_FRACTIONS"] = g["show_fractions"]
        if g["x_start"] is not None:
            cfg["X_START"] = g["x_start"]
        if g["x_end"] is not None:
            cfg["X_END"] = g["x_end"]
        cfg["Y_OFFSET_UV"] = g["y_offset_uv"]
        if g["y_min_uv"] is not None:
            cfg["Y_MIN_UV"] = g["y_min_uv"]
        if g["y_max_uv"] is not None:
            cfg["Y_MAX_UV"] = g["y_max_uv"]
        cfg["FIG_SIZE"] = list(g["fig_size"])

        files = []
        for p in self.filepage.list.paths():
            fc = self.file_controls.get(p)
            if not fc:
                continue
            c = fc.to_config()
            if not c["types"]:
                continue
            entry = {"FILENAME": c["path"], "TYPE": c["types"]}
            if c["color"]:
                entry["COLOR"] = c["color"]
            if c["uv_offset"] is not None:
                entry["UV_OFFSET"] = c["uv_offset"]
            if c["scaling_factor"] != 1:
                entry["SCALING_FACTOR"] = c["scaling_factor"]
            if c["legend_label"]:
                entry["LEGEND_LABEL"] = c["legend_label"]
            if c["fraction_groups"]:
                entry["FRACTION_GROUPS"] = c["fraction_groups"]
            files.append(entry)
        cfg["FILES"] = files

        try:
            with open(path, "w") as f:
                yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
            self.status.setText(f"Config → {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))

    # ------------------------------------------------------------------ close
    def closeEvent(self, e):
        self.thread.quit()
        self.thread.wait(2000)
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        super().closeEvent(e)


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
