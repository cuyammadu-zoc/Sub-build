import os
import sys
from markitdown import MarkItDown

def convert_documents(input_dir="docs", output_dir="docs/markdown"):
    """Converts PDFs, Office files, and images inside docs/ into Markdown."""
    md = MarkItDown()
    os.makedirs(output_dir, exist_ok=True)
    
    if not os.path.exists(input_dir):
        print(f"[MARKITDOWN] Directory '{input_dir}' does not exist. Skipping.")
        return

    supported_exts = ('.pdf', '.docx', '.xlsx', '.pptx', '.html', '.csv', '.png', '.jpg')
    
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith(supported_exts):
                file_path = os.path.join(root, file)
                out_name = f"{os.path.splitext(file)[0]}.md"
                out_path = os.path.join(output_dir, out_name)
                
                print(f"[MARKITDOWN] Converting {file} -> {out_name}")
                try:
                    result = md.convert(file_path)
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(result.text_content)
                    print(f"[SUCCESS] Wrote {out_path}")
                except Exception as e:
                    print(f"[ERROR] Failed to convert {file}: {e}")

if __name__ == "__main__":
    convert_documents()
