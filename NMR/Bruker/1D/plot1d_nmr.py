import matplotlib.pyplot as plt
import numpy as np
import nmrglue as ng
import yaml
import argparse
import logging
from pathlib import Path
import matplotlib as mpl
mpl.rcParams["mathtext.fontset"] = "dejavuserif" # nicer omega symbol
mpl.rcParams["contour.negative_linestyle"] = "solid" # make negative contours solid

logging.basicConfig( level=logging.INFO, format='[%(levelname)s] %(message)s')

def apply_seaborn_style(param_dict):
    import seaborn as sns
    sns.set_theme(**param_dict)


def make_ppm_scale(dic):
    """Create ppm scale from dic (Bruker)"""
    SF = dic["procs"]["SF"]
    SW_p = dic["procs"]["SW_p"]
    SI = dic["procs"]["SI"]
    OFFSET = dic["procs"]["OFFSET"]
    ppm_scale = np.linspace( OFFSET, OFFSET - SW_p / SF, SI, endpoint=False)
    
    return ppm_scale

def get_max_between_ppm(ppm_scale, data, ppm=[2.4, 2.7], mode="max"):
    """Return max/min of data between two ppm values, independent of axis direction."""

    ppm_low, ppm_high = sorted(ppm)   # ensure correct order

    # find boolean mask for ppm range
    mask = (ppm_scale >= ppm_low) & (ppm_scale <= ppm_high)

    if not np.any(mask):
        raise ValueError(f"No data points found in ppm range {ppm}")

    region = data[mask]

    if mode == "max":
        return np.max(region)
    elif mode == "min":
        return np.min(region)
    else:
        raise ValueError("mode must be 'max' or 'min'")


def plot_data(input_list, output_name, xlimits, ylimits, x_axis_label, scale_range, scale_mode, figure_size):

    if figure_size is not None:
        plt.figure(figsize=figure_size)
    else:
        plt.figure()

    for spectrum_data in input_list:
        fname, color, label, offset, scale_factor = spectrum_data # unpack the input list 
        offset = float(offset)
        scale_factor = float(scale_factor)

        # read in the data from the Bruker folder
        dic, data = ng.bruker.read_pdata(fname)
        data = data * scale_factor

        # make ppm scale
        ppm_scale = make_ppm_scale(dic)

        if scale_range is not None:
            max_val = get_max_between_ppm(ppm_scale, data, ppm=scale_range, mode=scale_mode)
            data = data / max_val
        data = data + offset

        plt.plot(ppm_scale, data, color=color, label=label)

    plt.xlabel(x_axis_label)

    if xlimits is not None:
        x_start, x_end = xlimits
        x_start = float(x_start)
        x_end = float(x_end)
        plt.xlim((x_start, x_end))
    if ylimits is not None:
        y_start, y_end = ylimits
        y_start = float(y_start)
        y_end = float(y_end)
        plt.ylim((y_start, y_end))
    
    plt.yticks([])
    plt.legend()
    plt.gca().invert_xaxis()
    #plt.show()
    plt.savefig(output_name, dpi=600, bbox_inches='tight')



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
    output_folder.mkdir(parents=True, exist_ok=True)
    
    output_name = cfg.get('OUTPUT_NAME', 'output_plot')
    if not output_name.endswith('.png'):
        output_name += '.png'
    output_name = Path(output_folder) / output_name
    
    xlimits = cfg.get('X_LIM', None)
    ylimits = cfg.get('Y_LIM', None)

    x_axis_label = cfg.get('X_AXIS_LABEL', r"$^{1}$H [ppm]")
    figure_size = cfg.get('FIG_SIZE', None)

    scale_range_raw = cfg.get('SCALE_RANGE', None)
    if scale_range_raw is not None:
        scale_range = scale_range_raw[:2]
        scale_mode = scale_range_raw[-1]
    else:
        scale_range = None
        scale_mode = None
    



    all_input_list = []
    for entry in file_entries:
        fname     = Path(entry['FILENAME']) / "pdata" / "1"
        color   = entry.get('COLOR', None)
        label  = entry.get('LABEL', None)
        offset = entry.get('OFFSET', 0)
        scale_factor = entry.get('SCALE_FACTOR', 1.0)

        file_input_list = [fname, color, label, offset, scale_factor]
        all_input_list.append(file_input_list)

    # Do Plotting
    plot_data(all_input_list, output_name, xlimits, ylimits, x_axis_label, scale_range, scale_mode, figure_size)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot 1D NMR data from ucsf files.")
    parser.add_argument(
        "yaml_config",
        nargs="?",
        default=None,
        help="Path to the YAML configuration file (default: ./input.yaml)"
    )
    
    args = parser.parse_args()

    if args.yaml_config is None:
        logging.info("No YAML specified, defaulting to ./input.yaml")
        args.yaml_config = "input.yaml"
    
    main(args.yaml_config)