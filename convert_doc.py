import os
import sys
import re
import argparse
import unicodedata
from pathlib import Path
from docling.document_converter import DocumentConverter, PdfFormatOption, WordFormatOption, PowerpointFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, CodeFormulaVlmOptions
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

def main():
    parser = argparse.ArgumentParser(description="Convert documents to Markdown with images.")
    parser.add_argument("input_document", help="Path to the input document (PDF, DOCX, PPTX)")
    parser.add_argument("--output-dir", default="output", help="Directory to save the output (default: output/)")
    parser.add_argument("--device", choices=["cpu", "cuda", "auto"], default="auto", help="Device to use for PDF conversion (default: auto)")
    args = parser.parse_args()

    input_path = Path(args.input_document)
    if not input_path.exists():
        print(f"Error: Input document '{args.input_document}' not found.")
        sys.exit(1)

    ext = input_path.suffix.lower()
    if ext not in FORMAT_MAP:
        print(f"Error: Unsupported format '{ext}'. Supported formats: {', '.join(FORMAT_MAP.keys())}")
        sys.exit(1)

    doc_name = input_path.stem
    output_dir = Path(args.output_dir) / doc_name
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_md = output_dir / f"{doc_name}.md"
    image_dir = output_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    input_format = FORMAT_MAP[ext]
    device = detect_device() if args.device == "auto" else args.device

    print(f"Initializing conversion for {args.input_document} (Format: {input_format.name})...")
    
    if input_format == InputFormat.PDF:
        print(f"Using device: {device} for PDF processing")
        # Configure CodeFormulaV2 preset and custom scale
        code_formula_options = CodeFormulaVlmOptions.from_preset("codeformulav2")
        code_formula_options.scale = 3.0  # Increased for higher-resolution crops

        # Configure Pipeline Options for PDF
        pipeline_options = PdfPipelineOptions()
        pipeline_options.accelerator_options.device = device
        pipeline_options.generate_picture_images = True
        pipeline_options.images_scale = 2.0  # Overall pipeline scale
        pipeline_options.do_formula_enrichment = True
        pipeline_options.code_formula_options = code_formula_options

        converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF],
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        )
    else:
        # For DOCX and PPTX, no GPU pipeline is used/needed in the same way
        converter = DocumentConverter(
            allowed_formats=[input_format]
        )
    
    # Convert
    print("Converting document...")
    result = converter.convert(input_path)
    
    from docling_core.types.doc.base import ImageRefMode
    
    print("Exporting to Markdown and saving images (auto-mapping references)...")
    result.document.save_as_markdown(
        filename=output_md,
        artifacts_dir=Path("images"),
        image_mode=ImageRefMode.REFERENCED
    )
    
    # Antigravity IDE markdown previewer works best with explicit relative paths
    with open(output_md, "r", encoding="utf-8") as f:
        md_content = f.read()
        
    md_content = md_content.replace("](images/", "](./images/")
    
    # Clean LaTeX spacing and handle fallback Unicode math
    print("Post-processing: cleaning LaTeX spacing and converting fallback Unicode math...")
    cleaned_content = clean_latex_spacing(md_content)
    final_content = fallback_unicode_math(cleaned_content)
    
    with open(output_md, "w", encoding="utf-8") as f:
        f.write(final_content)
            
    print(f"\nConversion Summary:")
    print(f"- Output File: {output_md}")
    print(f"- Image Directory: {image_dir}")
    if input_format == InputFormat.PDF:
        print(f"- GPU Utilization: {'Enabled (CUDA)' if device == 'cuda' else 'Disabled (CPU)'}")

if __name__ == "__main__":
    main()
