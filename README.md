# docs-to-md

A unified tool to convert PDF, DOCX, and PPTX documents into Markdown, complete with image extraction and automatic formatting.

## Setup

### Prerequisites

Python must be installed on your system before running the setup scripts.

* **Windows:**
  Download and install Python 3.10+ from the official website: [python.org/downloads](https://www.python.org/downloads/).
  > [!IMPORTANT]
  > During installation on Windows, make sure to check the box **"Add python.exe to PATH"**.

* **Linux (Debian / Ubuntu):**
  Install Python 3, pip, and the venv package using your package manager:
  ```bash
  sudo apt update
  sudo apt install -y python3 python3-pip python3-venv
  ```

### Installation

Initialize the environment and install dependencies. The setup script will automatically detect if an NVIDIA GPU is available and install the appropriate requirements:

| Platform | GPU detected | Requirements file |
|----------|--------------|-------------------|
| Linux / macOS | Yes | `requirements.txt` |
| Linux / macOS | No | `requirements-cpu.txt` |
| Windows | Yes | `requirements-windows.txt` |
| Windows | No | `requirements-cpu.txt` |

#### Linux / macOS
```bash
chmod +x setup_env.sh convert.sh
./setup_env.sh
```

### Windows
```cmd
setup_env.bat
```

> [!NOTE]
> GPU installs pull CUDA-enabled PyTorch (`+cu118`) from [PyTorch's wheel index](https://download.pytorch.org/whl/cu118).
>
> - **Windows:** `requirements-windows.txt` omits Linux-only NVIDIA wheels (`nvidia-cufile`, etc.); Windows PyTorch wheels bundle the CUDA runtime.
> - **Linux:** `requirements.txt` includes the full pinned NVIDIA stack.
>
> Python **3.10–3.12** is recommended for the pinned GPU stack. If you hit compatibility errors on 3.13, recreate the venv with an older interpreter (e.g. `python3.12 -m venv venv` on Linux, or `py -3.12 -m venv venv` on Windows).

## Usage

You have three ways to run the conversion:

1. **Batch Mode (Double-click)**
   Place your documents (PDF, DOCX, PPTX) into the `input/` folder, then simply double-click `convert.bat` (Windows) or run `./convert.sh` (Linux/macOS) with no arguments. It will automatically convert everything in the `input/` folder.
   
2. **Drag-and-Drop (Windows)**
   Drag a document file and drop it directly onto `convert.bat` in File Explorer.
   
3. **Command Line (Single file)**
   ```bash
   # Linux / macOS
   ./convert.sh path/to/document.pdf
   
   # Windows
   convert.bat path\to\document.pdf
   ```

### CLI Options (for advanced use)
```bash
# You can also run the Python script directly if the venv is activated
python convert_doc.py <input_document> [--output-dir DIR] [--device auto|cpu|cuda] [--memory-profile auto|low|high]
python convert_doc.py --batch [--output-dir DIR] [--device auto|cpu|cuda] [--memory-profile auto|low|high]
```

`--memory-profile` controls GPU memory tuning for PDF conversion:
- **`auto`** (default): uses the **low** profile when CUDA VRAM is 4 GiB or less; otherwise **high**
- **`low`**: smaller page/element batches, lower image scale, disabled torch compile — keeps GPU + formula enrichment but is slower
- **`high`**: maximum quality settings for GPUs with sufficient VRAM

## Output Structure

Outputs are generated in the `output/` directory (which is gitignored by default to prevent large binary and regenerable artifacts from cluttering the repo). 

```text
output/
└── <document_name>/
    ├── <document_name>.md
    └── images/
        ├── image_000000.png
        └── ...
```

## Verification

To verify the integrity of the generated Markdown against the original document, use `verify_integrity.py`:

```bash
python verify_integrity.py path/to/source.docx output/path/to/markdown.md [--keywords OCS API]
```
