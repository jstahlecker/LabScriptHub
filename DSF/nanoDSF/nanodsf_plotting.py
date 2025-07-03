import yaml
import logging
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import argparse
from pathlib import Path

logging.basicConfig( level=logging.INFO, format='[%(levelname)s] %(message)s')

def read_data(filename):
    """Read data from .xlsx"""
    df_overview    = pd.read_excel(filename, sheet_name='Overview', header=0)
    df_ratio       = pd.read_excel(filename, sheet_name='Ratio', header=0)
    df_first_deriv = pd.read_excel(filename, sheet_name='Ratio (1st deriv.)', header=0)
    return df_overview, df_ratio, df_first_deriv

def apply_seaborn_style(param_dict):
    import seaborn as sns
    sns.set_theme(**param_dict)

def filter_data(df_ratio, df_first_deriv, capillary_list):
    """Filter and extract arrays for specified capillaries"""
    # Clean column names
    df_ratio.columns       = [str(x).strip() for x in df_ratio.columns]
    df_first_deriv.columns = [str(x).strip() for x in df_first_deriv.columns]
    temps = df_ratio['Capillary'][2:].to_numpy().astype(float)
    data = {}
    for cap in capillary_list:
        cap_str = str(cap)
        if cap_str not in df_ratio.columns:
            raise KeyError(f"Capillary '{cap_str}' not found in Ratio sheet.")
        ratio_vec = df_ratio[cap_str][2:].to_numpy().astype(float)
        deriv_vec = df_first_deriv[cap_str][2:].to_numpy().astype(float)
        data[cap_str] = (temps, ratio_vec, deriv_vec)
    return data

def plot_combined(data_entries, output_path, temp_min=None, temp_max=None):
    """Plot all entries on a single figure, respecting optional colors"""
    fig, axes = plt.subplots(2, 1, sharex=True)
    default_colors = plt.rcParams['axes.prop_cycle'].by_key()['color']

    for idx, (temps, ratio, deriv, label, color) in enumerate(data_entries):
        # Apply temperature bounds
        mask = np.ones_like(temps, dtype=bool)
        if temp_min is not None:
            mask &= (temps >= temp_min)
        if temp_max is not None:
            mask &= (temps <= temp_max)
        t, r, d = temps[mask], ratio[mask], deriv[mask]

        # choose color: explicit or default palette
        plot_color = color if color else default_colors[idx % len(default_colors)]

        axes[0].plot(t, r, linewidth=0.7, color=plot_color)
        axes[1].plot(t, d, linewidth=0.7, color=plot_color, label=label)

    axes[0].set_ylabel('Ratio 350 nm / 330 nm')
    axes[1].set_xlabel('Temperature [°C]')
    axes[1].set_ylabel('First Derivative')
    axes[1].set_yticks([])
    axes[1].legend(fontsize=7)

    plt.subplots_adjust(hspace=0)
    fig.align_ylabels(axes[:])

    plt.savefig(output_path, dpi=600, bbox_inches='tight')
    plt.close(fig)


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

    # Global parameters
    output_folder = Path(cfg.get('OUTPUT_FOLDER', '.'))
    output_name   = cfg.get('OUTPUT_NAME', 'nanodsf_plot.png')
    if not Path(output_name).suffix:
        output_name += '.png'
    output_path   = output_folder / output_name
    temp_min      = cfg.get('TEMP_MIN', None)
    temp_max      = cfg.get('TEMP_MAX', None)
    


    combined_entries = []
    for entry in file_entries:
        fn     = entry['FILENAME']
        caps   = entry['CAPILLARY_LIST']
        color_list  = entry.get('COLOR_LIST', None)
        label_list  = entry.get('LABEL_LIST', None)

        df_ov, df_r, df_fd = read_data(fn)
        data = filter_data(df_r, df_fd, caps)
        for idx, cap in enumerate(caps):
            cap_str = str(cap)
            temps, ratio, deriv = data[cap_str]
            color = color_list[idx] if color_list and idx < len(color_list) else None
            label = label_list[idx] if label_list and idx < len(label_list) else None
            # derive label from Overview sheet
            mask = df_ov['Capillary'].astype(str) == cap_str
            if label:
                label = label
            elif mask.any():
                label = df_ov.loc[mask, 'Sample ID'].iloc[0]
            else:
                label = f"{Path(fn).stem}_Cap{cap_str}"
            combined_entries.append((temps, ratio, deriv, label, color))

    plot_combined(combined_entries, output_path, temp_min, temp_max)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Plot combined data from multiple Excel files using a single YAML config.')
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
