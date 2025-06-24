# LabScriptHub

**LabScriptHub** is a collection of scripts for plotting and data analysis tailored to various laboratory instruments and experimental setups. The repository is organized into subdirectories based on experiment type or machine, offering tools for data preprocessing, visualization, and interpretation.

## 📁 Directory Structure

The repository is structured as follows:

- **`DSF/`**  
  Scripts for Differential Scanning Fluorimetry (DSF) data analysis.  
  - **`nanoDSF/`**: Scripts and configurations for nanoDSF experiments.  
  - **`Qiagen_RotorGeneQ/`**: Preprocessing scripts for DSF data from the Qiagen Rotor-Gene Q machine.
  -  **`Origin/`**: A small Add-on script to automate smoothing, differentiation and basic peak detection using Origin.

- **`ITC/`**  
  Scripts for Isothermal Titration Calorimetry (ITC) data analysis.  
  - **`itc200/`**: Tools for ITC data visualization and final figure generation.  

- **`NMR/`**  
  Scripts for Nuclear Magnetic Resonance (NMR) data analysis.  
  - **`Bruker/`**: Tools for processing and plotting 1D and 2D NMR data.  

- **`Optical_Assays/`**  
  Scripts for optical assay data preprocessing and analysis.  
  - **`CLARIOstar/`**: Preprocessing scripts for fluorescence polarization assays.  

🛠 YAML configuration files are used to streamline input/output handling and parameter customization.

---

## 🚀 Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/LabScriptHub.git
   cd LabScriptHub
   ```

2. **Set up the environment** (recommended using `conda`):
   ```bash
   conda create -n LabScriptHub python
   conda activate LabScriptHub
   ```

3. **Install required packages**:
   ```bash
   pip install -r requirements.txt
   ```

---

## 🤝 Contributing, Bugs & Requests

If you have ideas for new features, improvements, or bug fixes, feel free to message me.

---