import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import sys

from itc_final_figure import *




# Create a simple GUI to select file and set options
class ITCFinalFigureGUI:
    def __init__(self, master):
        self.master = master
        master.title("ITC Final Figure Generator")

        # File selection
        self.file_label = tk.Label(master, text="Input CSV File:")
        self.file_label.grid(row=0, column=0, sticky="e")
        self.file_entry = tk.Entry(master, width=40)
        self.file_entry.grid(row=0, column=1)
        self.browse_button = tk.Button(master, text="Browse...", command=self.browse_file)
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

    def browse_file(self):
        file_path = filedialog.askopenfilename(
            title="Select input CSV file",
            filetypes=[("CSV files", "*.csv")]
        )
        if file_path:
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, file_path)

    def run(self):
        input_file_path = self.file_entry.get()
        sep = self.sep_entry.get()
        decimal = self.decimal_entry.get()
        energy_unit = self.energy_entry.get()

        if not input_file_path:
            print("No file selected. Exiting.")
            return

        INPUT_FILE = Path(input_file_path)
        output_file = INPUT_FILE.parent / (INPUT_FILE.stem + ".png")

        df = pd.read_csv(INPUT_FILE, sep=sep, decimal=decimal)
        plot_itc(df, output_file, energy_unit=energy_unit)
        print(f"Figure saved to {output_file}")
        plt.close("all")
        self.master.destroy()
        sys.exit(0)

# Run the GUI
if __name__ == "__main__":
    root = tk.Tk()
    gui = ITCFinalFigureGUI(root)
    root.mainloop()
