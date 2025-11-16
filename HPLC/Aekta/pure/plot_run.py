import matplotlib.pyplot as plt
import pandas as pd
import yaml
import argparse
import logging
import sys
from pathlib import Path
import matplotlib as mpl

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

uv_colors = {
    "UV_280": "tab:blue",
    "UV_260": "tab:orange",
    "UV_230": "tab:red",
}

def apply_seaborn_style(param_dict):
    import seaborn as sns
    sns.set_theme(**param_dict)

def get_columns(fn, what_to_plot):
    """
    Gets the column index where the requested data is stored in the file.
    If what_to_plot is "UV_280", finds a column whose name contains both "UV" and "280".
    Otherwise, looks for an exact header match.
    """
    # Read only the second line of the file
    try:
        with open(fn, 'r', encoding="utf-16") as f:
            f.readline()  # skip first line
            second_line = f.readline().strip()
            header = second_line.split('\t')

    except UnicodeDecodeError as e:
        logging.info(f"Error reading file {fn}: {e} with encoding UTF-16. Trying UTF-8.")
        with open(fn, 'r', encoding="utf-8") as f:
            f.readline()  # skip first line
            second_line = f.readline().strip()
            header = second_line.split(',')

        
    

    # Special case: UV_280 needs both tokens in one header cell
    try:
        if what_to_plot.startswith("UV_"):
            token1, token2 = what_to_plot.split('_')
            for idx, col_name in enumerate(header):
                if token1 in col_name and token2 in col_name:
                    return idx
            raise ValueError(f"No column containing both '{token1}' and '{token2}' found in headers: {header}")

    except ValueError as e:
        uv_index = header.index("UV")
        logging.warning(f"Assuming there is only one UV in the file (Column index {uv_index}). Using that for '{what_to_plot}'.")
        return uv_index


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

def compute_plot_order(what_to_plot):
    """
    Plot order policy:
      - Plot all non-UV traces first (keep input order).
      - Then plot UV traces in reverse input order so that the first
        listed UV wavelength is plotted last (on top).
    """
    uv = [t for t in what_to_plot if t.startswith("UV_")]
    non_uv = [t for t in what_to_plot if not t.startswith("UV_")]
    return non_uv + uv[::-1]

def plot_run(input_list, global_params):
    """
    input_list: list of (Path or filename, list of plot_type strings,
                        fraction groups, color, uv_offset_override,
                        scaling_factor, legend_label)
    """

    fig, ax_left = plt.subplots(figsize=(10, 6))
    ax_right = ax_left.twinx()

    plotted_on_left = False
    plotted_on_right = False
    y_min_left = None
    y_max_left = None
    fractions_drawn = False
    non_uv_types_seen = set()

    for fn, what_to_plot, fraction_group, file_color, file_uv_offset, scaling_factor, legend_label in input_list:
        logging.info(f"Processing file: {fn}")
        try:
            df = pd.read_csv(fn, header=2, delimiter='\t', encoding='UTF-16')
        except UnicodeDecodeError as e:
            logging.info(f"Error reading file {fn}: {e} with encoding UTF-16. Trying UTF-8.")
            df = pd.read_csv(fn, header=2, delimiter=',', encoding='UTF-8')

        what_to_plot_sorted = compute_plot_order(what_to_plot)
        print(f"Plotting in order: {what_to_plot_sorted}")

        for plot_type in what_to_plot_sorted:
            col_idx = get_columns(fn, plot_type)
            if col_idx is None:
                raise ValueError(f"Column for '{plot_type}' not found in file: {fn}")

            x = df.iloc[:, col_idx].values
            y = df.iloc[:, col_idx + 1].values.astype(float)

            if "UV" in plot_type:
                ax = ax_left
                plotted_on_left = True
                if legend_label:
                    label = legend_label
                else:
                    try:
                        label = f"UV ({plot_type.split('_')[1]} nm)"
                    except IndexError:
                        label = "UV"
                y_offset = file_uv_offset if file_uv_offset is not None else global_params['y_offset_UV']
                y = (y * scaling_factor) + y_offset
                color = file_color or uv_colors.get(plot_type, None)
            else:
                ax = ax_right
                plotted_on_right = True
                non_uv_types_seen.add(plot_type)
                if plot_type == "Conc B":
                    color = "tab:green"
                    label = "Concentration B"
                elif plot_type == "Cond":
                    color = "tab:brown"
                    label = "Conductivity"
                else:
                    color = None
                    label = plot_type

            ax.plot(x, y, label=label, color=color)

        if global_params['show_fractions'] and not fractions_drawn:
            try:
                f_ml_index = get_columns(fn, "Fraction")
                f_ml = df.iloc[:, f_ml_index].dropna().values
                f_no = df.iloc[:, f_ml_index + 1].dropna().values
            except ValueError as exc:
                logging.warning(f"Could not draw fractions for {fn}: {exc}")
            else:
                fractions_drawn = True
                for index, fraction in enumerate(f_ml):
                    if index == 0 or (index + 1) % 5 == 0:
                        ax_left.axvline(x=fraction, ymin=0, ymax=0.07, color="grey", linewidth=0.6)
                        text = f_no[index]
                        if "Waste" not in text:
                            ax_left.text(
                                fraction,
                                0.07,
                                text,
                                transform=ax_left.get_xaxis_transform(),
                                ha="center",
                                va="bottom",
                                size=8,
                                rotation=22.5,
                            )
                    ax_left.axvline(x=fraction, ymin=0, ymax=0.05, color="grey", linewidth=0.6)

        if fraction_group is not None:
            y_min_current = ax_left.get_ylim()[0]
            for fraction in fraction_group:
                f_ml_index = get_columns(fn, "Fraction")
                f_no_index = f_ml_index + 1
                f_ml = df.iloc[:, f_ml_index].dropna().values
                f_no = df.iloc[:, f_no_index].dropna().values
                frac_start = fraction["START"]
                frac_end = fraction["END"]

                frac_start_index = get_fraction_index(f_no, frac_start)
                frac_end_index = get_fraction_index(f_no, frac_end) + 1
                area_color = fraction.get('COLOR', 'blue')
                uv_type = next((t for t in what_to_plot if "UV" in t), None)
                if uv_type is None:
                    continue
                col_uv = get_columns(fn, uv_type)
                x_uv = df.iloc[:, col_uv].values
                y_uv = df.iloc[:, col_uv + 1].values.astype(float)
                uv_offset = file_uv_offset if file_uv_offset is not None else global_params['y_offset_UV']
                y_uv = (y_uv * scaling_factor) + uv_offset
                i0, i1 = sorted([frac_start_index, frac_end_index])
                i0 = max(0, i0)
                i1 = min(i1, len(f_ml) - 1)

                x0, x1 = f_ml[i0], f_ml[i1]

                m = (x_uv >= x0) & (x_uv <= x1)
                if m.any():
                    baseline = (
                        global_params['y_min_uv']
                        if global_params['y_min_uv'] is not None
                        else y_min_current
                    )
                    ax_left.fill_between(
                        x_uv,
                        y_uv,
                        baseline,
                        where=m,
                        interpolate=True,
                        color=area_color,
                        alpha=0.2,
                    )

        current_min, current_max = ax_left.get_ylim()
        y_min_left = current_min if y_min_left is None else min(y_min_left, current_min)
        y_max_left = current_max if y_max_left is None else max(y_max_left, current_max)

    ax_left.set_xlabel('Volume [mL]')

    if plotted_on_left:
        ax_left.set_ylabel('Absorption [mAU]')
    if plotted_on_right:
        if "Conc B" in non_uv_types_seen:
            ax_right.set_ylabel('Concentration [%]')
        elif "Cond" in non_uv_types_seen:
            ax_right.set_ylabel('Conductivity [mS/cm]')

    handles_left, labels_left = ax_left.get_legend_handles_labels()
    handles_right, labels_right = ax_right.get_legend_handles_labels()
    all_handles = handles_left + handles_right
    all_labels = labels_left + labels_right

    ax_left.legend(all_handles, all_labels, loc='best')
    if not plotted_on_right:
        ax_right.set_visible(False)

    if global_params['x_start'] is not None and global_params['x_end'] is not None:
        ax_left.set_xlim(global_params['x_start'], global_params['x_end'])
    elif global_params['x_start'] is not None:
        ax_left.set_xlim(global_params['x_start'], ax_left.get_xlim()[1])
    elif global_params['x_end'] is not None:
        ax_left.set_xlim(ax_left.get_xlim()[0], global_params['x_end'])

    if plotted_on_left:
        if y_min_left is None or y_max_left is None:
            y_min_left, y_max_left = ax_left.get_ylim()
        y_lower, y_upper = y_min_left, y_max_left
        if global_params['y_min_uv'] is not None:
            y_lower = global_params['y_min_uv']
        if global_params['y_max_uv'] is not None:
            y_upper = global_params['y_max_uv']
        ax_left.set_ylim(y_lower, y_upper)

    ax_left.xaxis.set_minor_locator(mpl.ticker.MultipleLocator(10))
    ax_left.tick_params(axis='y', which='both', left=True, labelleft=True)
    plt.tight_layout()
    plt.savefig(global_params['output_name'], dpi=600)


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


    seaborn_flag = cfg.get('USE_SEABORN', False)
    if seaborn_flag:
        seaborn_params = cfg.get('SEABORN_PARAMS', {"style": "ticks", "context": "paper"})
        apply_seaborn_style(seaborn_params)

    file_entries = cfg.get('FILES', [])
    if not file_entries:
        raise ValueError("Config YAML must contain a 'FILES' list with at least one entry.")

    # global parameters
    # make default name
    first_filename_as_default = Path(file_entries[0]["FILENAME"]).stem + ".png"

    global_params = {
        'show_fractions': cfg.get('SHOW_FRACTIONS', False),
        'x_start': cfg.get('X_START', None),
        'x_end': cfg.get('X_END', None),
        'output_name': make_output_name(cfg.get('OUTPUT_FOLDER', '.'), cfg.get('OUTPUT_NAME') or first_filename_as_default),
        'y_offset_UV': cfg.get('Y_OFFSET_UV', 0),
        'y_min_uv': cfg.get('Y_MIN_UV', None),
        'y_max_uv': cfg.get('Y_MAX_UV', None),
    }
    

    
    all_plot_data = []
    for entry in file_entries:
        if 'FILENAME' not in entry:
            logging.error("Each entry in 'FILES' must contain a 'FILENAME' key.")
            sys.exit(1)
        
        fn = Path(entry['FILENAME'])
        what_to_plot = entry.get('TYPE', [])
        if not what_to_plot:
            logging.error("Each entry in 'FILES' must contain a 'TYPE' key with the data type to plot.")
            sys.exit(1)
        uv_count = sum(1 for t in what_to_plot if "UV" in t)
        different_plot_types = len(what_to_plot) - uv_count
        if different_plot_types > 2:
            logging.error("Config YAML 'TYPE' key must contain at most two different data types.")
            sys.exit(1)
        if not any("UV" in t for t in what_to_plot):
            logging.error("Config YAML 'TYPE' key must contain at least one 'UV' type.")
            sys.exit(1)
        fraction_group = entry.get('FRACTION_GROUPS', None)

        file_color = entry.get('COLOR')
        file_uv_offset = (
            entry.get('UV_OFFSET', entry.get('UV_Offset', entry.get('Y_OFFSET_UV')))
        )
        if file_uv_offset is not None:
            try:
                file_uv_offset = float(file_uv_offset)
            except (TypeError, ValueError):
                logging.error(f"Invalid UV offset '{file_uv_offset}' for file {fn}.")
                sys.exit(1)

        scaling_factor = entry.get('SCALING_FACTOR', 1)
        try:
            scaling_factor = float(scaling_factor)
        except (TypeError, ValueError):
            logging.error(f"Invalid SCALING_FACTOR '{scaling_factor}' for file {fn}.")
            sys.exit(1)

        legend_label = entry.get('LEGEND_LABEL', entry.get('LEGEND'))

        all_plot_data.append(
            (
                fn,
                what_to_plot,
                fraction_group,
                file_color,
                file_uv_offset,
                scaling_factor,
                legend_label,
            )
        )

    plot_run(all_plot_data, global_params)

        



if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Plot data from an ÄKTA chromatography run using a YAML config.')
    parser.add_argument(
        "yaml_config",
        nargs="?",
        default=None,
        help="Path to the YAML configuration file (default: ./input.yaml)"
    )
    args = parser.parse_args()
    if args.yaml_config is None:
        logging.info("No YAML config provided, using default: ./input.yaml")
        args.yaml_config = './input.yaml'  # Default config file
    main(args.yaml_config)
