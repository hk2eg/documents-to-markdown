# docs-to-md

A unified tool to convert PDF, DOCX, and PPTX documents into Markdown, complete with image extraction and automatic formatting.

## Setup

First, initialize the environment and install dependencies. The setup script will automatically detect if an NVIDIA GPU is available and install the appropriate requirements (`requirements.txt` for GPU, `requirements-cpu.txt` for CPU-only).

### Linux / macOS
```bash
chmod +x setup_env.sh convert.sh
./setup_env.sh
```

### Windows
```cmd
setup_env.bat
```

> [!NOTE]
> GPU users on Windows will use the fully-pinned `requirements.txt` which includes CUDA/cuDNN packages proven to work on the company's MX lineup NVIDIA GPUs.

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
python convert_doc.py <input_document> [--output-dir DIR] [--device auto|cpu|cuda]
python convert_doc.py --batch [--output-dir DIR] [--device auto|cpu|cuda]
```

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
