import matplotlib.pyplot as plt
import nmrglue as ng
import numpy as np
import yaml
import argparse
from pathlib import Path
import matplotlib as mpl
mpl.rcParams["mathtext.fontset"] = "dejavuserif" # nicer omega symbol
mpl.rcParams["contour.negative_linestyle"] = "solid" # make negative contours solid


def hsqc_plot(input_list, output_name, xlimits, ylimits):
    ### Plotting stuff ###

    fig = plt.figure()
    ax = fig.add_subplot(111)
    default_colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
    color_iter = iter(default_colors)
    # loop over the files, colors and contour start

    legend_info = []
    labels = []
    for spectrum_data in input_list:
        fname, color, label, cl, neg_list = spectrum_data # unpack the input list 

        # read in the data from the Sparky (.ucsf) file
        dic, data = ng.sparky.read(fname)

        # make ppm scales for both dimensions.
        uc_x = ng.sparky.make_uc(dic, data, dim=1)
        x0, x1 = uc_x.ppm_limits()
        uc_y = ng.sparky.make_uc(dic, data, dim=0)
        y0, y1 = uc_y.ppm_limits()

        # plot the contours
        if color is None:
            color = next(color_iter) # get the next color from the default color cycle
        
        contour = ax.contour(data, cl, colors=color, extent=(x0, x1, y0, y1), linewidths=0.5)
        labels.append(label)
        legend_info.append(contour.legend_elements()[0][0])

        # if neg_list is not None:
        if neg_list is not None:
            
            neg_color, neg_contours, neg_label = neg_list # unpack the negative list

            if neg_color is None:
                neg_color = next(color_iter) # get the next color from the default color cycle
            
            contour = ax.contour(data, neg_contours, colors=neg_color, extent=(x0, x1, y0, y1), linewidths=0.5)
            if neg_label is not None:
                labels.append(neg_label)
                legend_info.append(contour.legend_elements()[0][0]) # add the negative contour

    # decorate the axes and set limits
    ax.set_ylabel(r"$\omega_1 - ^{15}$N [ppm]")
    ax.set_xlabel(r"$\omega_2 - ^{1}$H [ppm]")

    if xlimits is not None:
        x0, x1 = xlimits
    if ylimits is not None:
        y0, y1 = ylimits
    
    ax.set_xlim(x0, x1) # set x limits
    ax.set_ylim(y0, y1) # set y limits


    #rect1 = patches.Rectangle((8.9, 133), -0.9, -10, fc='none', ec='black', lw=1, zorder=2)
    #rect2 = patches.Rectangle((7.65, 123.5), -0.7, -7, fc='none', ec='black', lw=1, zorder=2)
    #ax.add_patch(rect1)
    #ax.add_patch(rect2)


    #Create a legend for the contour set
    legend = ax.legend(legend_info, labels, loc="upper left", fontsize=10)
    for line in legend.get_lines():
        line.set_linewidth(2) 

        
    plt.tight_layout()

    fig.savefig(f"{output_name}", dpi=600) 
    

def main(yaml_config):
    # Load YAML config
    with open(yaml_config, 'r') as f:
        cfg = yaml.safe_load(f)

    file_entries = cfg.get('FILES', [])
    if not file_entries:
        raise ValueError("Config YAML must contain a 'FILES' list with at least one entry.")

    # Global parameters
    output_folder = cfg.get('OUTPUT_FOLDER', '.')
    output_name = cfg.get('OUTPUT_NAME', 'output_plot')
    if not output_name.endswith('.png'):
        output_name += '.png'
    output_name = Path(output_folder) / output_name
    
    xlimits = cfg.get('X_LIM', None)
    ylimits = cfg.get('Y_LIM', None)


    all_input_list = []
    for entry in file_entries:
        fname     = Path(entry['FILENAME'])
        color   = entry.get('COLOR', None)
        label  = entry['LABEL']
        contour = float(entry['CONTOUR'])
        contour_num = entry.get('CONTOUR_NUM', 14)
        contour_factor = entry.get('CONTOUR_FACTOR', 1.4)
        negative = entry.get('NEGATIVE', False)

        cl = contour * contour_factor ** np.arange(contour_num)

        if negative:
            neg_color = negative.get("COLOR", None)
            neg_label = negative.get("LABEL", None)
            neg_contours = -1 * cl
            neg_contours = (-cl)[::-1]

            neg_list = [neg_color, neg_contours, neg_label]
        else:
            neg_list = None
        
                

        file_input_list = [fname, color, label, cl, neg_list]
        all_input_list.append(file_input_list)


    # Do Plotting
    hsqc_plot(all_input_list, output_name, xlimits, ylimits)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot 2D NMR data from ucsf files.")
    parser.add_argument(
        "yaml_config",
        nargs="?",
        default=None,
        help="Path to the YAML configuration file (default: ./input.yaml)"
    )
    
    args = parser.parse_args()

    if args.yaml_config is None:
        print("No YAML specified, defaulting to ./input.yaml")
        args.yaml_config = "input.yaml"
    
    main(args.yaml_config)