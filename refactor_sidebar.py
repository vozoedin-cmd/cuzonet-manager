import os
import re

template_dir = r"c:\Desktop\Control total\PROYECTO 1\templates"

# Busca el bloque del sidebar, ignorando espacios o saltos de linea
pattern = re.compile(r'<!-- Sidebar -->\s*<nav class="sidebar">.*?</nav>', re.DOTALL)
pattern_no_comment = re.compile(r'<nav class="sidebar">.*?</nav>', re.DOTALL)

for filename in os.listdir(template_dir):
    if not filename.endswith('.html') or filename == 'sidebar.html':
        continue
        
    filepath = os.path.join(template_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if pattern.search(content):
        new_content = pattern.sub("{% include 'sidebar.html' %}", content)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Refactored {filename} (with comment)")
    elif pattern_no_comment.search(content):
        new_content = pattern_no_comment.sub("{% include 'sidebar.html' %}", content)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Refactored {filename} (no comment)")
    else:
        print(f"Skipped {filename} (no sidebar found)")
