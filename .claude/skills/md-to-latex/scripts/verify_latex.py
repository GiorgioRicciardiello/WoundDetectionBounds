#!/usr/bin/env python3
r"""
verify_latex.py — Zero-?? Verification for LaTeX Projects

Checks that a generated LaTeX project will compile without unresolved
references (?? marks). Validates:
  1. All \includegraphics files exist
  2. All \input{tables/...} files exist
  3. All \input{sections/...} files exist
  4. Every \ref has a matching \label
  5. Every parent \label has a matching \ref (subfigure labels exempt)
  6. Every \cite has a matching bib entry (or zero \cite if bib is placeholder)

Usage:
    python verify_latex.py <project_dir>
    python verify_latex.py publication-latex/

Exit codes:
    0 = all checks pass
    1 = one or more checks failed
"""

import re
import sys
from pathlib import Path


def find_tex_files(project_dir: Path) -> list[Path]:
    """Find all .tex files in the project."""
    return list(project_dir.rglob("*.tex"))


def extract_pattern(files: list[Path], pattern: str) -> dict[str, list[str]]:
    """Extract regex matches from files. Returns {match: [file_paths]}."""
    results: dict[str, list[str]] = {}
    regex = re.compile(pattern)
    for fpath in files:
        text = fpath.read_text(encoding="utf-8", errors="ignore")
        for match in regex.findall(text):
            results.setdefault(match, []).append(str(fpath))
    return results


def check_includegraphics(project_dir: Path, tex_files: list[Path]) -> list[str]:
    """Check that all \\includegraphics files exist in figures/."""
    figures_dir = project_dir / "figures"
    pattern = r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}"
    refs = extract_pattern(tex_files, pattern)
    errors = []
    for filename, sources in refs.items():
        target = figures_dir / filename
        if not target.exists():
            errors.append(
                f"MISSING figure: {filename} "
                f"(referenced in {', '.join(sources)})"
            )
    return errors


def check_input_files(project_dir: Path, tex_files: list[Path]) -> list[str]:
    """Check that all \\input files exist."""
    pattern = r"\\input\{([^}]+)\}"
    refs = extract_pattern(tex_files, pattern)
    errors = []
    for input_path, sources in refs.items():
        # \input{} paths are relative to project root, may omit .tex
        target = project_dir / input_path
        if not target.exists():
            target_with_ext = project_dir / (input_path + ".tex")
            if not target_with_ext.exists():
                errors.append(
                    f"MISSING input: {input_path} "
                    f"(referenced in {', '.join(sources)})"
                )
    return errors


def check_label_ref_integrity(
    tex_files: list[Path],
) -> tuple[list[str], list[str], list[str]]:
    """Check label <-> ref integrity. Returns (orphan_labels, dangling_refs, warnings)."""
    label_pattern = r"\\label\{([^}]+)\}"
    ref_pattern = r"\\(?:eq)?ref\{([^}]+)\}"

    labels = extract_pattern(tex_files, label_pattern)
    refs = extract_pattern(tex_files, ref_pattern)

    label_keys = set(labels.keys())
    ref_keys = set(refs.keys())

    # Dangling refs = refs without labels (will produce ??)
    dangling = []
    for key in sorted(ref_keys - label_keys):
        dangling.append(
            f"DANGLING ref: \\ref{{{key}}} has no \\label "
            f"(in {', '.join(refs[key])})"
        )

    # Orphan labels = labels without refs
    # Subfigure labels are exempt (their parent should be referenced)
    orphans = []
    warnings = []
    for key in sorted(label_keys - ref_keys):
        sources = labels[key]
        # Check if this is a subfigure label by looking for subfigure env
        is_subfigure = False
        for src in sources:
            text = Path(src).read_text(encoding="utf-8", errors="ignore")
            # Find the label and check if it's inside a subfigure
            label_positions = [
                m.start() for m in re.finditer(rf"\\label\{{{re.escape(key)}\}}", text)
            ]
            for pos in label_positions:
                # Look backward for \begin{subfigure}
                preceding = text[max(0, pos - 500) : pos]
                if "\\begin{subfigure}" in preceding:
                    last_begin = preceding.rfind("\\begin{subfigure}")
                    last_end = preceding.rfind("\\end{subfigure}")
                    if last_begin > last_end:
                        is_subfigure = True
                        break

        if is_subfigure:
            warnings.append(f"OK (subfigure): \\label{{{key}}} has no direct \\ref")
        elif key.startswith("eq:"):
            warnings.append(f"WARNING: equation \\label{{{key}}} has no \\ref")
        else:
            orphans.append(
                f"ORPHAN label: \\label{{{key}}} has no \\ref "
                f"(in {', '.join(sources)})"
            )

    return orphans, dangling, warnings


def check_citations(project_dir: Path, tex_files: list[Path]) -> list[str]:
    """Check that every \\cite has a matching bib entry."""
    bib_file = project_dir / "references.bib"

    # Extract cite keys
    cite_pattern = r"\\cite[tp]?\{([^}]+)\}"
    cite_refs = extract_pattern(tex_files, cite_pattern)

    # Flatten multi-key citations (e.g., \cite{a,b,c})
    all_cite_keys: dict[str, list[str]] = {}
    for keys_str, sources in cite_refs.items():
        for key in keys_str.split(","):
            key = key.strip()
            if key:
                all_cite_keys.setdefault(key, []).extend(sources)

    if not all_cite_keys:
        return []  # No citations = no problem

    # Extract bib keys
    bib_keys: set[str] = set()
    if bib_file.exists():
        bib_text = bib_file.read_text(encoding="utf-8", errors="ignore")
        bib_keys = set(re.findall(r"^@\w+\{([^,]+)", bib_text, re.MULTILINE))

    errors = []
    if not bib_keys:
        errors.append(
            f"FAIL: {len(all_cite_keys)} \\cite{{}} command(s) found but "
            f"references.bib has no entries — all will produce ??"
        )
        for key, sources in sorted(all_cite_keys.items()):
            errors.append(f"  \\cite{{{key}}} in {', '.join(set(sources))}")
    else:
        for key, sources in sorted(all_cite_keys.items()):
            if key not in bib_keys:
                errors.append(
                    f"MISSING bib entry: \\cite{{{key}}} "
                    f"(in {', '.join(set(sources))})"
                )

    return errors


def main() -> int:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <project_dir>")
        return 1

    project_dir = Path(sys.argv[1])
    if not project_dir.is_dir():
        print(f"Error: {project_dir} is not a directory")
        return 1

    tex_files = find_tex_files(project_dir)
    if not tex_files:
        print(f"Error: No .tex files found in {project_dir}")
        return 1

    print(f"Verifying LaTeX project: {project_dir}")
    print(f"Found {len(tex_files)} .tex files\n")

    all_errors: list[str] = []
    all_warnings: list[str] = []

    # 1. Check includegraphics
    print("=" * 60)
    print("1. Checking \\includegraphics file existence...")
    errors = check_includegraphics(project_dir, tex_files)
    all_errors.extend(errors)
    if errors:
        for e in errors:
            print(f"   {e}")
    else:
        print("   PASS")

    # 2. Check input files
    print("\n2. Checking \\input file existence...")
    errors = check_input_files(project_dir, tex_files)
    all_errors.extend(errors)
    if errors:
        for e in errors:
            print(f"   {e}")
    else:
        print("   PASS")

    # 3. Check label/ref integrity
    print("\n3. Checking \\label / \\ref integrity...")
    orphans, dangling, warnings = check_label_ref_integrity(tex_files)
    all_errors.extend(dangling)  # Dangling refs are errors (produce ??)
    all_warnings.extend(orphans)  # Orphan labels are warnings
    all_warnings.extend(warnings)  # Subfigure exemptions

    if dangling:
        print("   DANGLING REFS (will produce ??):")
        for d in dangling:
            print(f"   {d}")
    if orphans:
        print("   ORPHAN LABELS (no matching ref):")
        for o in orphans:
            print(f"   {o}")
    if warnings:
        for w in warnings:
            print(f"   {w}")
    if not dangling and not orphans:
        print("   PASS")

    # 4. Check citations
    print("\n4. Checking \\cite / .bib integrity...")
    errors = check_citations(project_dir, tex_files)
    all_errors.extend(errors)
    if errors:
        for e in errors:
            print(f"   {e}")
    else:
        print("   PASS (no \\cite commands or all matched)")

    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    if all_errors:
        print(f"\nFAILED: {len(all_errors)} error(s) found")
        print("These WILL produce ?? or compilation errors:\n")
        for i, e in enumerate(all_errors, 1):
            print(f"  {i}. {e}")
        if all_warnings:
            print(f"\n{len(all_warnings)} warning(s):")
            for w in all_warnings:
                print(f"  - {w}")
        return 1
    else:
        print("\nPASSED: Zero errors. Project should compile without ??.")
        if all_warnings:
            print(f"\n{len(all_warnings)} warning(s) (non-blocking):")
            for w in all_warnings:
                print(f"  - {w}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
