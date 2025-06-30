import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path
import yaml
import argparse


def apply_seaborn_style(param_dict):
    import seaborn as sns
    sns.set_theme(**param_dict)

def get_visible_label_boxes(axis):
    # Returns a list of (label_text, bounding_box) for visible y-tick labels
    boxes = []
    yticks = axis.get_yticks()
    yticklabels = axis.get_yticklabels()
    ymin, ymax = axis.get_ylim()
    renderer = plt.gcf().canvas.get_renderer()
    for tick, label in zip(yticks, yticklabels):
        if ymin <= tick <= ymax and label.get_text().strip():
            bbox = label.get_window_extent(renderer=renderer)
            boxes.append((label.get_text(), bbox))
    return boxes

def bboxes_overlap(bbox1, bbox2, padding=2):
    # Simple overlap test (with optional small padding)
    return not (bbox1.x1 + padding < bbox2.x0 or
                bbox1.x0 - padding > bbox2.x1 or
                bbox1.y1 + padding < bbox2.y0 or
                bbox1.y0 - padding > bbox2.y1)

def has_overlap(ax, index1, index2):
    boxes1 = get_visible_label_boxes(ax[index1])
    boxes2 = get_visible_label_boxes(ax[index2])
    # Check if any bounding boxes overlap
    for label1, bbox1 in boxes1:
        for label2, bbox2 in boxes2:
            if bboxes_overlap(bbox1, bbox2):
                return True
    return False

def plot_itc(df, output, energy_unit):

    time = df["DP_X"]
    dh = df["DP_Y"]

    Molar_Ratio_Raw = df["NDH_X"]
    NDH_Raw = df["NDH_Y"]
    Molar_Ratio_Fit = df["Fit_X"]
    NDH_Fit = df["Fit_Y"]

    # Create figure
    #fig, ax = plt.subplots(3, 1, figsize=(3.2,5))
    fig, ax = plt.subplots(3, 1, figsize=(3.2,6, ), gridspec_kw={'height_ratios': [1, 1, 0.2]})
    # Plot raw data
    ax[0].plot(time, dh, '-', color="black", label='raw data', linewidth=0.6)
    ax[0].set_xlabel('Time [min]')
    ax[0].set_ylabel('µcal / sec')
    # The x label and x ticks should be above the plot
    ax[0].xaxis.tick_top()
    ax[0].xaxis.set_label_position('top')
    # ax[0].axhline(y=0, color='red', linewidth=0.8)
    ax[0].tick_params(axis='both', which='major', labelsize=8)
    

    # Plot fitted data as squares
    ax[1].scatter(Molar_Ratio_Raw, NDH_Raw, marker='s', color="black", label='NDH', sizes=(10,10))
    ax[1].plot(Molar_Ratio_Fit, NDH_Fit, '-', color="black", label='DH', linewidth=0.8)
    #ax[1].set_xlabel('Molar Ratio')
    ax[1].set_ylabel(f'{energy_unit} of injectant')
    ax[1].tick_params(axis='both', which='major', labelsize=8)

    # Plot Residuals
    # Remove all Nan values of df["NDH_Y"] and df["Fit_Y"]
    ndh_y = df["NDH_Y"].to_numpy()
    fit_y = df["Fit_Y"].to_numpy()
    ndh_x = df["NDH_X"].to_numpy() # Same as Molar_Ratio_Raw
    fit_x = df["Fit_X"].to_numpy()

    # Remove all Nan values
    ndh_y = ndh_y[~np.isnan(ndh_y)]
    fit_y = fit_y[~np.isnan(fit_y)]
    ndh_x = ndh_x[~np.isnan(ndh_x)]
    fit_x = fit_x[~np.isnan(fit_x)]

    # Make (x,y) pairs so that we can calculate the residuals if the x value is the same
    ndh = np.column_stack((ndh_x, ndh_y))
    fit = np.column_stack((fit_x, fit_y))

    # Find the residuals
    residuals = []
    for i in range(len(ndh)):
        for j in range(len(fit)):
            if ndh[i][0] == fit[j][0]:
                residuals.append((fit[j][0] ,ndh[i][1] - fit[j][1]))

    res_x = [i[0] for i in residuals]
    res_y = [i[1] for i in residuals]


    ax[2].scatter(res_x, res_y, marker='s', color="black", label='NDH', sizes=(10,10))
    ax[2].set_xlabel('Molar Ratio')
    ax[2].set_ylabel('Residuals')
    ax[2].axhline(y=0, color='black', linewidth=0.8)
    
    # the y zero should be in the middle of the plot
    max_res = max([abs(i) for i in res_y])
    lower_limit = round(-max_res - 0.1, 1)
    upper_limit = round(max_res + 0.1, 1)
    buffer_size = 0.1

    ax[2].set_ylim([lower_limit - buffer_size, upper_limit + buffer_size])
    ax[2].tick_params(axis='both', which='major', labelsize=8)
    ax[2].set_yticks([lower_limit, 0, upper_limit])


    # The spacing between the two plots should be removed
    plt.subplots_adjust(hspace=0)
    fig.align_ylabels(ax[:])
    
    plt.draw()
    has_overlap_bool = has_overlap(ax, 1, 2)

    # Add to the buffer size until there is no overlap
    while has_overlap_bool:
        buffer_size += 0.2
        ax[2].set_ylim([lower_limit - buffer_size, upper_limit + buffer_size])
        ax[2].tick_params(axis='both', which='major', labelsize=8)
        ax[2].set_yticks([lower_limit, 0, upper_limit])
        plt.draw()  # Ensures ticks/labels are updated
        has_overlap_bool = has_overlap(ax, 1, 2)

    # Sanity Check for Plots 0 and 1
    has_overlap_bool = has_overlap(ax, 0, 1)
    new_buffer_size = 0.1
    while has_overlap_bool:
        new_buffer_size += 0.2
        ax[1].set_ylim([ax[1].get_ylim()[0], ax[1].get_ylim()[1] + new_buffer_size])
        plt.draw()  # Ensures ticks/labels are updated
        has_overlap_bool = has_overlap(ax, 0, 1)

    # Save figure
    common_xlim = ax[1].get_xlim()       
    ax[1].set_xlim(common_xlim)
    ax[2].set_xlim(common_xlim)


    ax[1].tick_params(axis='x', which='both',
                  bottom=False, top=False, labelbottom=False)

    plt.savefig(output, dpi=600, bbox_inches='tight')


def main(yaml_config: Path):

    # Load YAML
    with open(yaml_config, 'r') as f:
        cfg = yaml.safe_load(f)
    
    seaborn_flag = cfg.get('USE_SEABORN', False)
    if seaborn_flag:
        seaborn_params = cfg.get('SEABORN_PARAMS', {"style": "ticks", "context": "paper"})
        apply_seaborn_style(seaborn_params)


    # Required
    input_file = Path(cfg['FILENAME'])
    # Optional
    energy_unit         = cfg.get('ENERGY_UNIT', 'kcal / mol')
    output_folder        = Path(cfg.get('OUTPUT_FOLDER', '.'))
    output_name          = cfg.get('OUTPUT_NAME', f"{input_file.stem}")
    delimiter            = cfg.get('DELIMITER', ',')
    decimal              = cfg.get('DECIMAL', '.')

    # Prepare output folder
    output_folder.mkdir(parents=True, exist_ok=True)

    # Check if output filename has .xlsx extension
    if not output_name.endswith('.png'):
        output_name += '.png'
    
    output_name = output_folder / output_name

    
    # Load df
    #df = pd.read_csv(input_file, sep=';', decimal=',')
    df = pd.read_csv(input_file, sep=delimiter, decimal=decimal)
    plot_itc(df, output_name, energy_unit)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Plot ITC data from a CSV file.")
    parser.add_argument('yaml_config', 
                        nargs='?', 
                        default=None,
                        help='Path to the YAML configuration file (default: ./input.yaml)')

    args = parser.parse_args()
    if args.yaml_config is None:
        print("No YAML config provided, using default: ./input.yaml")
        args.yaml_config = './input.yaml'  # Default config file

    main(args.yaml_config)