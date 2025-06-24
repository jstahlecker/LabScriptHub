# LabScriptHub

LabScriptHub is a collection of scripts for plotting and analysis tailored to various laboratory machines and experimental setups. This repository is organized into subdirectories based on the type of experiment or machine, providing tools for data preprocessing, visualization, and analysis.

## Directory Structure

The repository is organized as follows:

- **DSF/**  
  Scripts for Differential Scanning Fluorimetry (DSF) data analysis.  
  - **nanoDSF/**: Contains scripts and configurations for nanoDSF experiments.  
  - **Qiagen_RotorGeneQ/**: Includes preprocessing scripts for DSF data from the Qiagen Rotor-Gene Q machine.  

- **ITC/**  
  Scripts for Isothermal Titration Calorimetry (ITC) data analysis.  
  - **itc200/**: Tools for ITC data visualization and final figure generation.  

- **NMR/**  
  Scripts for Nuclear Magnetic Resonance (NMR) data analysis.  
  - **Bruker/**: Contains tools for processing and plotting 1D and 2D NMR data.  

- **Optical_Assays/**  
  Scripts for optical assay data preprocessing and analysis.  
  - **CLARIOstar/**: Includes preprocessing scripts for fluorescence polarization assays.  

YAML configuration files are used to streamline input/output handling and parameter customization.  

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/LabScriptHub.git
   cd LabScriptHub

2. Install requirements
   I suggest to create a new env (e.g. using conda):
   ```bash
   conda create -n LabScriptHub python
   