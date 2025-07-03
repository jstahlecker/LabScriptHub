import pandas as pd
from pathlib import Path
import argparse
import logging
import yaml

logging.basicConfig( level=logging.INFO, format='[%(levelname)s] %(message)s')

def read_data(file_path: Path) -> pd.DataFrame:
    """
    Read an Excel file into a DataFrame.
    """
    return pd.read_excel(file_path, engine="xlrd")


def reorganize(data_df: pd.DataFrame) -> dict:
    """
    Take the raw DataFrame and pull out Temperature (col “X”) plus
    each sample’s fluorescence column, renaming to ensure uniqueness.
    """
    data = {'Temperature': data_df['X']}
    sample_name_counter = {}
    
    # Each sample block is 3 columns: name, temp, fluorescence
    for i in range(0, len(data_df.columns), 3):
        name_col = data_df.columns[i]
        temp_col = data_df.columns[i+1]
        fluo_col = data_df.columns[i+2]

        # Extract the “Sample:Foo” -> “Foo”
        raw_name = data_df[name_col][0]
        sample_name = raw_name.split(':', 1)[1].strip()

        # Make unique
        count = sample_name_counter.get(sample_name, 0) + 1
        sample_name_counter[sample_name] = count
        unique_name = f"{sample_name}_{count}"

        # Sanity-check that all temperatures line up
        if not (data_df[temp_col] == data['Temperature']).all():
            raise ValueError(f"Temperature mismatch in column {temp_col!r}")

        data[unique_name] = data_df[fluo_col]

    return data

def main(yaml_config: Path):
    # 1) Load YAML
    with open(yaml_config, 'r') as f:
        cfg = yaml.safe_load(f)
    in_file    = Path(cfg['FILENAME'])
    out_folder = Path(cfg.get('OUTPUT_FOLDER', '.'))
    out_folder.mkdir(parents=True, exist_ok=True)

    # 2) Read & reshape
    df = read_data(in_file)
    data = reorganize(df)
    result_df = pd.DataFrame(data)

    # 3) Determine output name
    out_name = cfg.get('OUTPUT_NAME', f"preprocessed_{in_file.stem}")
    # Check if out_name has .xlsx extension
    if not out_name.endswith('.xlsx'):
        out_name += '.xlsx'
    out_path = out_folder / out_name

    # 4) Write
    result_df.to_excel(out_path, index=False)
    logging.info("Written reorganized data to %s", out_path)

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
