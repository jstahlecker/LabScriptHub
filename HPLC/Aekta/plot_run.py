import matplotlib.pyplot as plt
import pandas as pd
import yaml
import argparse
from pathlib import Path
import matplotlib as mpl

uv_colors = {
    "UV_280": "tab:blue",
    "UV_260": "tab:orange",
    "UV_230": "tab:red",
}


def get_columns(fn, what_to_plot):
    """
    Gets the column index where the requested data is stored in the file.
    If what_to_plot is "UV_280", finds a column whose name contains both "UV" and "280".
    Otherwise, looks for an exact header match.
    """
    # Read only the second line of the file
    with open(fn, 'r', encoding="utf-16") as f:
        f.readline()  # skip first line
        second_line = f.readline().strip()
        header = second_line.split('\t')
    

    # Special case: UV_280 needs both tokens in one header cell
    if what_to_plot == "UV_280":
        token1, token2 = what_to_plot.split('_')
        for idx, col_name in enumerate(header):
            if token1 in col_name and token2 in col_name:
                return idx
        raise ValueError(f"No column containing both '{token1}' and '{token2}' found in headers: {header}")

    # General case: exact match in header list
    if what_to_plot in header:
        return header.index(what_to_plot)
    else:
        raise ValueError(f"'{what_to_plot}' not found in headers: {header}")

def get_fraction_index(f_no, f_name):

    # Get the index of f_name in f_no
    try:
        index = f_no.tolist().index(f_name)
    except ValueError:
        raise ValueError(f"Fraction '{f_name}' not found in f_no list: {f_no}")
    return index


def plot_run(input_list, global_params):
    """
    input_list: list of (Path or filename, list of plot_type strings)
    """

    # Create main figure + left axis
    fig, ax_left = plt.subplots(figsize=(10, 6))
    # Create right axis that shares the same x-axis
    ax_right = ax_left.twinx()

    # Keep track of which axes have had data plotted, for legends
    plotted_on_left = False
    plotted_on_right = False

    if len(input_list) == 1:

        for fn, what_to_plot, fraction_group in input_list:
            df = pd.read_csv(fn, header=2, delimiter='\t', encoding='UTF-16')

            for plot_type in what_to_plot:
                # Find the column index for this plot_type
                col_idx = get_columns(fn, plot_type)
                if col_idx is None:
                    raise ValueError(f"Column for '{plot_type}' not found in file: {fn}")

                # Extract x and y
                x = df.iloc[:, col_idx].values
                y = df.iloc[:, col_idx + 1].values

                # Choose axis based on plot_type
                if "UV" in plot_type:
                    ax = ax_left
                    plotted_on_left = True
                    label = f"UV ({plot_type.split('_')[1]} nm)"
                    color = uv_colors.get(plot_type, None)
                else:
                    ax = ax_right
                    plotted_on_right = True
                    if plot_type == "Conc B":
                        color = "tab:green"
                        label = "Concentration B"
                    elif plot_type == "Cond":
                        color = "tab:brown"
                        label = "Conductivity"

                # Plot
                ax.plot(x, y, label=label, color=color)

            if global_params['show_fractions']:
                f_ml_index = get_columns(fn, "Fraction")
                f_no_index = f_ml_index + 1
                f_ml = df.iloc[:, f_ml_index].dropna().values
                f_no = df.iloc[:, f_no_index].dropna().values
                for index, fraction in enumerate(f_ml):
                    if index == 0 or (index + 1) % 5 == 0:
                        ax_left.axvline(x=fraction, ymin=0, ymax=0.07, color="grey", linewidth=0.6)
                        text = f_no[index]
                        if "Waste" not in text:
                            ax.text(fraction, 0.07*(ax.get_ylim()[1]-ax.get_ylim()[0])+ax.get_ylim()[0] ,text, ha="center", va="bottom", size=8, rotation=22.5)
                    ax_left.axvline(x=fraction, ymin=0, ymax=0.05, color="grey", linewidth=0.6)
                
            if fraction_group is not None:
                for fraction in fraction_group:
                    f_ml_index = get_columns(fn, "Fraction")
                    f_no_index = f_ml_index + 1
                    f_ml = df.iloc[:, f_ml_index].dropna().values
                    f_no = df.iloc[:, f_no_index].dropna().values
                    frac_start = fraction["START"]
                    frac_end = fraction["END"]

                    frac_start_index = get_fraction_index(f_no, frac_start)
                    frac_end_index = get_fraction_index(f_no, frac_end)
                    ax_left.axvspan(f_ml[frac_start_index], f_ml[frac_end_index], color='blue', alpha=0.1)

        ax_left.set_xlabel('Volume [mL]')

        # Set y-axis labels
        if plotted_on_left:
            ax_left.set_ylabel('Absorption [mAU]')
        if plotted_on_right:
            if "Conc B" in what_to_plot:
                ax_right.set_ylabel('Concentration [%]')
            elif "Cond" in what_to_plot:
                ax_right.set_ylabel('Conductivity [mS/cm]')

        # Build a combined legend
        handles_left, labels_left = ax_left.get_legend_handles_labels()
        handles_right, labels_right = ax_right.get_legend_handles_labels()
        all_handles = handles_left + handles_right
        all_labels  = labels_left  + labels_right

        # Place legend (you can tweak loc as needed)
        ax_left.legend(all_handles, all_labels, loc='upper left')
        if not plotted_on_right:
            ax_right.set_visible(False)
        
        # Set x-axis limits if specified
        if global_params['x_start'] is not None and global_params['x_end'] is not None:
            ax_left.set_xlim(global_params['x_start'], global_params['x_end'])
        elif global_params['x_start'] is not None:
            ax_left.set_xlim(global_params['x_start'], ax_left.get_xlim()[1])
        elif global_params['x_end'] is not None:
            ax_left.set_xlim(ax_left.get_xlim()[0], global_params['x_end'])
        
        # Add the x ticks
        # Configure ticks - only show on X-axis
        ax_left.xaxis.set_minor_locator(mpl.ticker.MultipleLocator(10))
        
        # If you want to keep the left y-axis label but hide ticks:
        ax_left.tick_params(axis='y', which='both', left=False, labelleft=True)
        plt.tight_layout()
        #plt.show()
        plt.savefig(global_params['output_name'], dpi=600)
    
    elif len(input_list) > 1:
        raise ValueError("Multiple files are not supported in this version of the script. Please provide a single file in the input list.")


def make_output_name(output_folder, output_name):
    """
    Constructs the full output path from the folder and file name.
    If the folder does not exist, it creates it.
    """
    if not output_name.endswith('.png'):
        output_name += '.png'
    output_path = Path(output_folder) / Path(output_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path
            

def main(yaml_config):
    # Load YAML config
    with open(yaml_config, 'r') as f:
        cfg = yaml.safe_load(f)

    file_entries = cfg.get('FILES', [])

    # global parameters

    global_params = {
        'show_fractions': cfg.get('SHOW_FRACTIONS', False),
        'x_start': cfg.get('X_START', None),
        'x_end': cfg.get('X_END', None),
        'output_name': make_output_name(cfg.get('OUTPUT_FOLDER', '.'), cfg.get('OUTPUT', 'aekta_plot.png'))
    }

    if not file_entries:
        raise ValueError("Config YAML must contain a 'FILES' list with at least one entry.")
    
    all_plot_data = []
    for entry in file_entries:
        if 'FILENAME' not in entry:
            raise ValueError("Each entry in 'FILES' must contain a 'FILENAME' key.")
        
        fn = Path(entry['FILENAME'])
        what_to_plot = entry.get('TYPE', [])
        if not what_to_plot:
            raise ValueError("Config YAML must contain a 'TYPE' key with the data type to plot.")
        elif len(what_to_plot) > 2:
            raise ValueError("Config YAML 'TYPE' key must contain at most two data types.")
        if not any("UV" in t for t in what_to_plot):
            raise ValueError("Config YAML 'TYPE' key must contain at least one 'UV' type.")
        fraction_group = entry.get('FRACTION_GROUPS', None)

        all_plot_data.append((fn, what_to_plot, fraction_group))

    plot_run(all_plot_data, global_params)

        




main("input.yaml")