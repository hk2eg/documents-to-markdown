import docx
import re
import os

def verify(docx_path, md_path):
    print(f"Starting integrity verification for {md_path}...")
    
    if not os.path.exists(docx_path):
        print(f"Error: Source file {docx_path} not found.")
        return
    if not os.path.exists(md_path):
        print(f"Error: Output file {md_path} not found.")
        return

    # 1. Inspect original DOCX
    doc = docx.Document(docx_path)
    docx_text = "\n".join([p.text for p in doc.paragraphs])
    docx_tables = doc.tables
    
    # Text statistics
    orig_chars = len(docx_text)
    orig_words = len(docx_text.split())
    orig_tables_count = len(docx_tables)
    
    # 2. Inspect generated Markdown
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()
    
    # Markdown statistics
    gen_chars = len(md_content)
    gen_words = len(md_content.split())
    
    # Improved table detection in MD: counting horizontal separators |---|
    md_table_count = len(re.findall(r'\n\|[-\s:|]+\|\n', md_content))
    
    print("\n--- Structural Comparison ---")
    print(f"{'Metric':<20} | {'Original':<10} | {'Converted':<10} | {'Status'}")
    print("-" * 60)
    
    # Char check (Markdown usually has more due to syntax, but shouldn't be drastically less)
    char_status = "PASS" if gen_chars > (orig_chars * 0.5) else "WARN (Low char count)"
    print(f"{'Characters':<20} | {orig_chars:<10} | {gen_chars:<10} | {char_status}")
    
    # Table check
    table_status = "PASS" if md_table_count >= orig_tables_count else f"WARN ({orig_tables_count - md_table_count} tables may be missing)"
    print(f"{'Tables':<20} | {orig_tables_count:<10} | {md_table_count:<10} | {table_status}")
    
    # 3. Keyword Content Check
    print("\n--- Content Integrity Check ---")
    keywords = ["OCS", "FixedData", "ISD", "OOTB", "API", "Egypt"]
    missing_keywords = []
    for kw in keywords:
        if kw.lower() in md_content.lower():
            print(f"- Keyword '{kw}': FOUND")
        else:
            print(f"- Keyword '{kw}': NOT FOUND")
            missing_keywords.append(kw)
            
    if not missing_keywords:
        print("\nAll core keywords found. Content appears intact.")
    else:
        print(f"\nWarning: Missing keywords: {', '.join(missing_keywords)}")

    print("\nVerification complete.")

if __name__ == "__main__":
    verify("ORG Egypt_FixedData OCS Project_ISD_OOTB API_V0.21_21012026.docx", "output.md")
