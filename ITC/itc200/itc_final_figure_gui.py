import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import sys

from itc_final_figure import plot_itc


# Create a simple GUI to select file and set options
class ITCFinalFigureGUI:
    def __init__(self, master):
        self.master = master
        master.title("ITC Final Figure Generator")

        self.file_paths = []

        # File selection
        self.file_label = tk.Label(master, text="Input CSV File:")
        self.file_label.grid(row=0, column=0, sticky="e")
        self.file_entry = tk.Entry(master, width=40)
        self.file_entry.grid(row=0, column=1)
        self.browse_button = tk.Button(master, text="Browse...", command=self.browse_files)
        self.browse_button.grid(row=0, column=2)

        # Separator
        self.sep_label = tk.Label(master, text="CSV Separator:")
        self.sep_label.grid(row=1, column=0, sticky="e")
        self.sep_entry = tk.Entry(master, width=5)
        self.sep_entry.insert(0, ",")
        self.sep_entry.grid(row=1, column=1, sticky="w")

        # Decimal
        self.decimal_label = tk.Label(master, text="Decimal Symbol:")
        self.decimal_label.grid(row=2, column=0, sticky="e")
        self.decimal_entry = tk.Entry(master, width=5)
        self.decimal_entry.insert(0, ".")
        self.decimal_entry.grid(row=2, column=1, sticky="w")

        # Energy unit
        self.energy_label = tk.Label(master, text="Energy Unit:")
        self.energy_label.grid(row=3, column=0, sticky="e")
        self.energy_entry = tk.Entry(master, width=15)
        self.energy_entry.insert(0, "kcal / mol")
        self.energy_entry.grid(row=3, column=1, sticky="w")

        # Run button
        self.run_button = tk.Button(master, text="Generate Figure", command=self.run)
        self.run_button.grid(row=4, column=1, pady=10)

    def browse_files(self):
        files = filedialog.askopenfilenames(
            title="Select one or more CSV files",
            filetypes=[("CSV files", "*.csv")]
        )
        if files:
            self.file_paths = list(files)
            # show just the first + count
            display = f"{Path(files[0]).name}"
            if len(files) > 1:
                display += f"  (+{len(files)-1} more)"
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, display)

    def run(self):
        if not self.file_paths:
            print("No files selected. Exiting.")
            return

        sep = self.sep_entry.get()
        decimal = self.decimal_entry.get()
        energy_unit = self.energy_entry.get()

        for fp in self.file_paths:
            inp = Path(fp)
            out = inp.parent / (inp.stem + ".png")
            df = pd.read_csv(inp, sep=sep, decimal=decimal)
            plot_itc(df, out, energy_unit=energy_unit)
            print(f"Figure saved to {out}")

        # cleanup
        plt.close("all")
        self.master.destroy()
        sys.exit(0)

# Run the GUI
if __name__ == "__main__":
    root = tk.Tk()
    gui = ITCFinalFigureGUI(root)
    root.mainloop()
