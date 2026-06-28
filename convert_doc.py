import os

# Must be set before docling/torch are imported (docling loads torch at import time).
# expandable_segments is not supported on Windows CUDA builds.
if os.name != "nt":
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import gc
import sys
import re
import argparse
import unicodedata
from pathlib import Path
from docling.document_converter import DocumentConverter, PdfFormatOption, WordFormatOption, PowerpointFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, CodeFormulaVlmOptions, TableFormerMode
from docling.datamodel.base_models import InputFormat

def unicode_math_to_ascii(ch):
    try:
        name = unicodedata.name(ch)
        if name.startswith('MATHEMATICAL'):
            parts = name.split()
            letter = parts[-1]
            if len(letter) == 1:
                return letter.lower() if 'SMALL' in name else letter
            greek_map = {
                'ALPHA': 'alpha', 'BETA': 'beta', 'GAMMA': 'gamma', 'DELTA': 'delta',
                'EPSILON': 'epsilon', 'ZETA': 'zeta', 'ETA': 'eta', 'THETA': 'theta',
                'IOTA': 'iota', 'KAPPA': 'kappa', 'LAMBDA': 'lambda', 'MU': 'mu',
                'NU': 'nu', 'XI': 'xi', 'OMICRON': 'omicron', 'PI': 'pi',
                'RHO': 'rho', 'SIGMA': 'sigma', 'TAU': 'tau', 'UPSILON': 'upsilon',
                'PHI': 'phi', 'CHI': 'chi', 'PSI': 'psi', 'OMEGA': 'omega',
                'LAMDA': 'lambda'
            }
            if letter in greek_map:
                latex_greek = '\\' + greek_map[letter]
                if 'CAPITAL' in name:
                    latex_greek = latex_greek.capitalize()
                return latex_greek
        elif name == 'MULTIPLICATION SIGN':
            return ' \\times '
        elif name == 'N-ARY SUMMATION':
            return ' \\sum '
    except ValueError:
        pass
    return ch

def is_math_char(ch):
    if ord(ch) <= 127:
        return False
    try:
        name = unicodedata.name(ch)
        return 'MATHEMATICAL' in name or name in ('MULTIPLICATION SIGN', 'N-ARY SUMMATION')
    except ValueError:
        return False

def clean_latex_spacing(text):
    # Match display equations $$ ... $$
    def clean_block(match):
        eq = match.group(1)
        # 1. Collapse multiple spaces
        eq = re.sub(r'\s+', ' ', eq)
        # 2. Fix spaced-out LaTeX commands, e.g., \ t o t a l -> \total
        eq = re.sub(r'\\([a-zA-Z](?:\s+[a-zA-Z])*)', lambda m: '\\' + m.group(1).replace(' ', ''), eq)
        # 3. Fix spaces inside sub/superscripts conservatively
        eq = re.sub(r'(_|\^)\{\s*([a-zA-Z](?:\s+[a-zA-Z])*)\s*\}', lambda m: m.group(1) + '{' + m.group(2).replace(' ', '') + '}', eq)
        # 4. Fix spaces inside \text{...}
        eq = re.sub(r'\\text\s*\{\s*([a-zA-Z](?:\s+[a-zA-Z])*)\s*\}', lambda m: '\\text{' + m.group(1).replace(' ', '') + '}', eq)
        return '$$' + eq.strip() + '$$'
        
    return re.sub(r'\$\$(.*?)\$\$', clean_block, text, flags=re.DOTALL)

def fallback_unicode_math(text):
    lines = text.split('\n')
    new_lines = []
    
    for line in lines:
        if not any(is_math_char(c) for c in line):
            new_lines.append(line)
            continue
            
        if line.strip().startswith('$$') or line.strip().startswith('!['):
            new_lines.append(line)
            continue
            
        # If it's a table row, process each cell individually
        if line.strip().startswith('|') and line.strip().endswith('|'):
            cells = line.split('|')
            new_cells = []
            for cell in cells:
                if any(is_math_char(c) for c in cell):
                    converted = ''.join(unicode_math_to_ascii(c) for c in cell)
                    stripped = converted.strip()
                    if stripped and not (stripped.startswith('$') and stripped.endswith('$')):
                        left_pad = len(converted) - len(converted.lstrip())
                        right_pad = len(converted) - len(converted.rstrip())
                        converted = (' ' * left_pad) + '$' + stripped + '$' + (' ' * right_pad)
                    new_cells.append(converted)
                else:
                    new_cells.append(cell)
            new_lines.append('|'.join(new_cells))
        else:
            converted = ''.join(unicode_math_to_ascii(c) for c in line)
            stripped = converted.strip()
            
            # If it looks like an equation (contains '=' or '\times' or similar)
            if '=' in stripped or '\\times' in stripped or '\\sum' in stripped:
                left_pad = len(converted) - len(converted.lstrip())
                right_pad = len(converted) - len(converted.rstrip())
                new_lines.append((' ' * left_pad) + '$$' + stripped + '$$' + (' ' * right_pad))
            else:
                new_lines.append(converted)
                
    return '\n'.join(new_lines)

FORMAT_MAP = {
    '.pdf': InputFormat.PDF,
    '.docx': InputFormat.DOCX,
    '.pptx': InputFormat.PPTX,
}

def detect_device():
    """Try CUDA, fall back to CPU."""
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"


def detect_gpu_vram_gib():
    """Return total CUDA VRAM in GiB, or None if unavailable."""
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.get_device_properties(0).total_memory / (1024**3)
    except Exception:
        pass
    return None


def detect_system_ram_gib():
    """Return total system RAM in GiB, or None if unavailable."""
    try:
        import psutil
        return psutil.virtual_memory().total / (1024**3)
    except Exception:
        pass
    return None


def resolve_gpu_profile(requested: str, device: str) -> str:
    """Resolve auto/low/high GPU profile from CLI and VRAM."""
    if requested != "auto":
        return requested
    vram = detect_gpu_vram_gib()
    if device == "cuda" and vram is not None and vram <= 4.0:
        return "low"
    return "high"


def resolve_memory_profile(requested: str) -> str:
    """Resolve auto/low/high host memory profile from CLI and system RAM."""
    if requested != "auto":
        return requested
    ram = detect_system_ram_gib()
    if ram is not None and ram <= 8.0:
        return "low"
    return "high"


def resolve_pdf_chunk_size(requested, memory_profile: str) -> int:
    """Resolve pages per chunk; 0 disables chunking."""
    if requested is not None:
        return max(0, requested)
    return 5 if memory_profile == "low" else 0


def apply_low_gpu_settings():
    """Apply global Docling settings for low-VRAM GPU conversion."""
    from docling.datamodel.settings import settings

    settings.perf.elements_batch_size = 1
    settings.inference.compile_torch_models = False
    configure_code_formula_vlm_batch()


def apply_low_memory_settings():
    """Apply global Docling settings for low host-RAM conversion."""
    from docling.datamodel.settings import settings

    settings.perf.page_batch_size = 1


def configure_code_formula_vlm_batch():
    """Shrink CodeFormula VLM batch size for low-VRAM GPUs."""
    from docling.models.stages.code_formula.code_formula_vlm_model import CodeFormulaVlmModel

    CodeFormulaVlmModel.elements_batch_size = 1


def release_cuda_memory():
    """Free cached CUDA allocations between documents."""
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def get_pdf_page_count(input_path: Path):
    """Return total page count for a PDF, or None on failure."""
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(str(input_path))
        try:
            return len(pdf)
        finally:
            pdf.close()
    except Exception:
        return None


def build_pdf_pipeline_options(
    device: str, gpu_profile: str, memory_profile: str
) -> PdfPipelineOptions:
    """Build PdfPipelineOptions tuned for GPU and host memory profiles."""
    pipeline_options = PdfPipelineOptions()
    pipeline_options.accelerator_options.device = device
    pipeline_options.generate_picture_images = True
    pipeline_options.do_formula_enrichment = True

    code_formula_options = CodeFormulaVlmOptions.from_preset("codeformulav2")

    if gpu_profile == "low":
        pipeline_options.images_scale = 1.0
        pipeline_options.accelerator_options.num_threads = 2
        pipeline_options.ocr_batch_size = 1
        pipeline_options.layout_batch_size = 1
        pipeline_options.table_batch_size = 1
        pipeline_options.table_structure_options.mode = TableFormerMode.FAST
        code_formula_options.max_size = 768
    else:
        pipeline_options.images_scale = 2.0
        code_formula_options.scale = 3.0

    if memory_profile == "low":
        pipeline_options.queue_max_size = 10

    pipeline_options.code_formula_options = code_formula_options
    return pipeline_options


def convert_pdf_document(converter: DocumentConverter, input_path: Path, chunk_size: int):
    """Convert a PDF, optionally in page-range chunks to bound host RAM."""
    page_count = get_pdf_page_count(input_path) if chunk_size else None
    if not chunk_size or not page_count or page_count <= chunk_size:
        return converter.convert(input_path).document

    docs = []
    for start in range(1, page_count + 1, chunk_size):
        end = min(start + chunk_size - 1, page_count)
        print(f"  Converting pages {start}-{end} of {page_count}...")
        try:
            res = converter.convert(input_path, page_range=(start, end))
            docs.append(res.document)
        except Exception as exc:
            print(f"  WARNING: pages {start}-{end} failed: {exc}")
        finally:
            gc.collect()
            release_cuda_memory()

    if not docs:
        raise RuntimeError("All page chunks failed to convert.")
    if len(docs) == 1:
        return docs[0]

    from docling_core.types.doc.document import DoclingDocument
    return DoclingDocument.concatenate(docs)


def format_device_line(device: str, gpu_profile: str, memory_profile: str) -> str:
    """Format device/profile log line for PDF conversion."""
    parts = [f"Using device: {device}"]
    parts.append(f"gpu profile: {gpu_profile}")
    parts.append(f"memory profile: {memory_profile}")

    vram = detect_gpu_vram_gib()
    if vram is not None:
        parts.append(f"VRAM: {vram:.1f} GiB")

    ram = detect_system_ram_gib()
    if ram is not None:
        parts.append(f"RAM: {ram:.1f} GiB")

    return " (".join([parts[0], ", ".join(parts[1:])]) + ") for PDF processing"


def convert_single_doc(
    input_path: Path,
    base_output_dir: Path,
    device: str,
    gpu_profile: str = "high",
    memory_profile: str = "high",
    chunk_size: int = 0,
):
    ext = input_path.suffix.lower()
    if ext not in FORMAT_MAP:
        print(f"Skipping '{input_path.name}': Unsupported format '{ext}'.")
        return False

    doc_name = input_path.stem
    output_dir = base_output_dir / doc_name
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_md = output_dir / f"{doc_name}.md"
    image_dir = output_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    input_format = FORMAT_MAP[ext]

    print(f"\nInitializing conversion for {input_path.name} (Format: {input_format.name})...")
    
    if input_format == InputFormat.PDF:
        print(format_device_line(device, gpu_profile, memory_profile))
        if chunk_size:
            page_count = get_pdf_page_count(input_path)
            if page_count:
                print(f"Chunked conversion: {chunk_size} pages/chunk ({page_count} pages total)")

        pipeline_options = build_pdf_pipeline_options(device, gpu_profile, memory_profile)

        converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF],
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        )
    else:
        converter = DocumentConverter(
            allowed_formats=[input_format]
        )
    
    print(f"Converting document {input_path.name}...")
    if input_format == InputFormat.PDF:
        document = convert_pdf_document(converter, input_path, chunk_size)
    else:
        document = converter.convert(input_path).document
    
    from docling_core.types.doc.base import ImageRefMode
    
    print("Exporting to Markdown and saving images (auto-mapping references)...")
    document.save_as_markdown(
        filename=output_md,
        artifacts_dir=Path("images"),
        image_mode=ImageRefMode.REFERENCED
    )
    
    with open(output_md, "r", encoding="utf-8") as f:
        md_content = f.read()
        
    md_content = md_content.replace("](images/", "](./images/")
    
    print("Post-processing: cleaning LaTeX spacing and converting fallback Unicode math...")
    cleaned_content = clean_latex_spacing(md_content)
    final_content = fallback_unicode_math(cleaned_content)
    
    with open(output_md, "w", encoding="utf-8") as f:
        f.write(final_content)
            
    print(f"\nConversion Summary for {input_path.name}:")
    print(f"- Output File: {output_md}")
    print(f"- Image Directory: {image_dir}")
    if input_format == InputFormat.PDF:
        gpu_line = f"- GPU Utilization: {'Enabled (CUDA)' if device == 'cuda' else 'Disabled (CPU)'}"
        gpu_line += f" (gpu profile: {gpu_profile}, memory profile: {memory_profile})"
        if chunk_size:
            gpu_line += f", chunked: {chunk_size} pages/chunk"
        print(gpu_line)
    return True

def main():
    parser = argparse.ArgumentParser(description="Convert documents to Markdown with images.")
    parser.add_argument("input_document", nargs="?", default=None, help="Path to the input document (PDF, DOCX, PPTX)")
    parser.add_argument("--batch", action="store_true", help="Convert all supported documents in the input/ directory")
    parser.add_argument("--output-dir", default="output", help="Directory to save the output (default: output/)")
    parser.add_argument("--device", choices=["cpu", "cuda", "auto"], default="auto", help="Device to use for PDF conversion (default: auto)")
    parser.add_argument(
        "--gpu-profile",
        choices=["auto", "low", "high"],
        default="auto",
        help="VRAM tuning for PDF model inference (default: auto; low when CUDA VRAM <= 4 GiB)",
    )
    parser.add_argument(
        "--memory-profile",
        choices=["auto", "low", "high"],
        default="auto",
        help="Host RAM tuning / PDF chunking (default: auto; low when system RAM <= 8 GiB)",
    )
    parser.add_argument(
        "--pdf-chunk-size",
        type=int,
        default=None,
        help="Pages per chunk for low-memory PDF conversion (default: auto = 5 when memory profile low, else off; 0 disables)",
    )
    args = parser.parse_args()

    device = detect_device() if args.device == "auto" else args.device
    gpu_profile = resolve_gpu_profile(args.gpu_profile, device)
    memory_profile = resolve_memory_profile(args.memory_profile)
    chunk_size = resolve_pdf_chunk_size(args.pdf_chunk_size, memory_profile)

    if gpu_profile == "low":
        apply_low_gpu_settings()
    if memory_profile == "low":
        apply_low_memory_settings()

    base_output_dir = Path(args.output_dir)

    if args.batch or args.input_document is None:
        print("Running in batch mode...")
        input_dir = Path("input")
        if not input_dir.exists():
            print("Error: 'input/' directory not found. Please create it and add documents.")
            sys.exit(1)
            
        success_count = 0
        total_count = 0
        for file_path in input_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in FORMAT_MAP:
                total_count += 1
                if convert_single_doc(
                    file_path, base_output_dir, device, gpu_profile, memory_profile, chunk_size
                ):
                    success_count += 1
                release_cuda_memory()
                    
        if total_count == 0:
            print("No supported documents found in 'input/' directory.")
        else:
            print(f"\nBatch Conversion Complete: {success_count}/{total_count} documents successfully converted.")
            
    else:
        input_path = Path(args.input_document)
        if not input_path.exists():
            print(f"Error: Input document '{args.input_document}' not found.")
            sys.exit(1)
        convert_single_doc(
            input_path, base_output_dir, device, gpu_profile, memory_profile, chunk_size
        )
        release_cuda_memory()

if __name__ == "__main__":
    main()
