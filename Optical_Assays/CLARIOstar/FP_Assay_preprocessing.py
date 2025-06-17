#!/usr/bin/env python3
import argparse
from pathlib import Path

import pandas as pd
import numpy as np
from uncertainties import ufloat
import yaml

def process_file(input_file: Path, output_folder: Path, output_name: str, skiprows=None, sheet_name="All Cycles", reference_standard="Standard S12"):
    # 1) Read the sheet, with skiprows if provided
    if skiprows is not None:
        df = pd.read_excel(input_file, sheet_name=sheet_name, skiprows=skiprows)
    else:
        df = pd.read_excel(input_file, sheet_name=sheet_name)

    # 2) Filter and reset index
    filtered_data = df.iloc[1:].reset_index(drop=True)

    # 3) Melt all polarization columns into one
    melted_data = pd.melt(
        filtered_data,
        id_vars=['Well\nRow', 'Well\nCol', 'Content', 'Group'],
        value_vars=filtered_data.columns[4:],
        var_name='Time',
        value_name='Polarization'
    )
    melted_data['Polarization'] = pd.to_numeric(melted_data['Polarization'], errors='coerce')

    # 4) Group & aggregate
    grouped = melted_data.groupby(['Group', 'Content'])['Polarization']
    summary = grouped.agg(
        Mean='mean',
        Std='std' # Pandas default is ddof=1, which is what we want
    )

    # 5) Flatten to DataFrame
    final = summary.reset_index()
    final.columns = ['Group', 'Content', 'Mean', 'Std']

    # 6) Sort by Group, then numerically by Content
    final['Content_Num'] = final['Content'].str.extract(r'(\d+)').astype(int)
    final = final.sort_values(['Group', 'Content_Num']).drop('Content_Num', axis=1)

    # 7) Create ufloats and subtract reference
    final['Mean_U'] = final.apply(lambda r: ufloat(r['Mean'], r['Std']), axis=1)
    refs = final[final['Content'] == reference_standard].set_index('Group')['Mean_U']
    final['Diff_U'] = final.apply(lambda r: r['Mean_U'] - refs[r['Group']], axis=1)
    final['Mean_SubRef'], final['Std_SubRef'] = zip(*final['Diff_U'].apply(lambda x: (x.n, x.s)))
    #final['Mean_SubRef'] = final.apply(lambda r: (r['Mean_U'] - refs[r['Group']]).n, axis=1)
    #final['Std_SubRef']  = final.apply(lambda r: (r['Mean_U'] - refs[r['Group']]).s, axis=1)

    # 8) Scale to the maximum per group
    max_subref = final.groupby('Group')['Mean_SubRef'].transform('max')
    final['Mean_Scaled'] = 100 * final['Mean_SubRef'] / max_subref
    final['Std_Scaled']  = 100 * final['Std_SubRef']  / max_subref

    # 9) Clean up interim columns
    #final = final.drop(columns=['Mean_U', 'Mean', 'Std', 'Mean_SubRef', 'Std_SubRef'], errors='ignore')
    final = final.drop(columns=['Mean_U', 'Diff_U'], errors='ignore')

    # 10) Write out
    output_file = output_folder / output_name
    final.to_excel(output_file, index=False)
    print(f"✔️ Processed data written to {output_file}")

def main(yaml_config: Path):
    # Load YAML
    with open(yaml_config, 'r') as f:
        cfg = yaml.safe_load(f)

    # Required
    input_file = Path(cfg['FILENAME'])
    # Optional
    output_folder        = Path(cfg.get('OUTPUT_FOLDER', '.'))
    output_name          = cfg.get('OUTPUT_NAME', f"preprocessed_{input_file.stem}")
    skiprows             = cfg.get('SKIPROWS', None)
    sheet_name           = cfg.get('SHEET_NAME', 'All Cycles')
    reference_standard   = cfg.get('REFERENCE_STANDARD', 'Standard S12')

    # Prepare output folder
    output_folder.mkdir(parents=True, exist_ok=True)

    # Check if output filename has .xlsx extension
    if not output_name.endswith('.xlsx'):
        output_name += '.xlsx'

    # Run
    process_file(input_file, output_folder, output_name=output_name, skiprows=skiprows, sheet_name=sheet_name, reference_standard=reference_standard)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Process a polarization-time Excel file per a YAML config.'
    )
    parser.add_argument('yaml_config', help='Path to your input.yaml')
    args = parser.parse_args()
    main(Path(args.yaml_config))
