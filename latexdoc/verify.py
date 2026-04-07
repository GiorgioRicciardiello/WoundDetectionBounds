import re, os, glob

def find_labels(text):
    return set(re.findall(r'\\label\{([^}]+)\}', text))

def find_refs(text):
    return set(re.findall(r'\\ref\{([^}]+)\}', text))

def find_cites(text):
    return re.findall(r'\\cite[pt]?\{([^}]+)\}', text)

def find_bibs(text):
    return set(re.findall(r'@\w+\{([^,]+),', text))

def find_figures(text):
    return re.findall(r'\\includegraphics(?:\[.*?\])?\{([^}]+)\}', text)

tex_files = glob.glob('**/*.tex', recursive=True)
all_text = ''
for f in tex_files:
    with open(f, encoding='utf-8') as fh:
        all_text += fh.read()

labels = find_labels(all_text)
refs   = find_refs(all_text)
cites  = find_cites(all_text)

with open('references.bib', encoding='utf-8') as bh:
    bibs = find_bibs(bh.read())

print('=== Orphan labels (defined but never \\ref-ed) ===')
for l in sorted(labels - refs):
    print('  WARN:', l)
if not (labels - refs):
    print('  None')

print('\n=== Dangling refs (\\ref without matching \\label) ===')
for r in sorted(refs - labels):
    print('  ERROR:', r)
if not (refs - labels):
    print('  None')

all_keys = set()
for c in cites:
    for k in c.split(','):
        all_keys.add(k.strip())
print('\n=== Missing bib entries ===')
miss = all_keys - bibs
for k in sorted(miss):
    print('  MISSING:', k)
if not miss:
    print('  All OK')

print('\n=== Figures ===')
for f in find_figures(all_text):
    ok = any(os.path.exists(p) for p in [
        f, 'figures/' + f,
        'figures/' + f + '.pdf',
        'figures/' + f + '.png'
    ])
    print(' ', f, '->', 'OK' if ok else 'MISSING')
