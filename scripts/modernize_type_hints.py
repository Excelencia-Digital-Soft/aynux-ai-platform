#!/usr/bin/env python3
"""
Script para modernizar type hints a sintaxis Python 3.10+.

Transformaciones:
- List[X] → list[X]
- Dict[X, Y] → dict[X, Y]
- Tuple[X, Y] → tuple[X, Y]
- Set[X] → set[X]
- Optional[X] → X | None
- Union[X, Y] → X | Y

Actualiza imports automáticamente.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Any


class TypeHintModernizer:
    """Modernizes Python type hints to 3.10+ syntax."""

    def __init__(self, dry_run: bool = False, verbose: bool = False):
        """
        Initialize modernizer.

        Args:
            dry_run: If True, only show changes without applying them
            verbose: If True, show detailed progress
        """
        self.dry_run = dry_run
        self.verbose = verbose
        self.stats = {
            "files_processed": 0,
            "files_modified": 0,
            "replacements": {
                "List": 0,
                "Dict": 0,
                "Tuple": 0,
                "Set": 0,
                "Optional": 0,
                "Union": 0,
            },
        }

    def modernize_file(self, file_path: Path) -> bool:
        """
        Modernize type hints in a single file.

        Args:
            file_path: Path to Python file

        Returns:
            True if file was modified
        """
        if not file_path.suffix == ".py":
            return False

        try:
            content = file_path.read_text(encoding="utf-8")
            original_content = content

            # Apply transformations
            content = self._replace_list_hints(content)
            content = self._replace_dict_hints(content)
            content = self._replace_tuple_hints(content)
            content = self._replace_set_hints(content)
            content = self._replace_optional_hints(content)
            content = self._replace_union_hints(content)

            # Update imports
            content = self._update_imports(content)

            # Check if modified
            if content != original_content:
                if self.dry_run:
                    print(f"[DRY RUN] Would modify: {file_path}")
                    if self.verbose:
                        self._show_diff(original_content, content, file_path)
                else:
                    file_path.write_text(content, encoding="utf-8")
                    if self.verbose:
                        print(f"✅ Modified: {file_path}")

                self.stats["files_modified"] += 1
                return True

            return False

        except Exception as e:
            print(f"❌ Error processing {file_path}: {e}", file=sys.stderr)
            return False

    def _replace_list_hints(self, content: str) -> str:
        """Replace List[X] with list[X]."""
        pattern = r'\bList\['
        matches = len(re.findall(pattern, content))
        if matches > 0:
            self.stats["replacements"]["List"] += matches
            content = re.sub(pattern, 'list[', content)
        return content

    def _replace_dict_hints(self, content: str) -> str:
        """Replace Dict[X, Y] with dict[X, Y]."""
        pattern = r'\bDict\['
        matches = len(re.findall(pattern, content))
        if matches > 0:
            self.stats["replacements"]["Dict"] += matches
            content = re.sub(pattern, 'dict[', content)
        return content

    def _replace_tuple_hints(self, content: str) -> str:
        """Replace Tuple[X, Y] with tuple[X, Y]."""
        pattern = r'\bTuple\['
        matches = len(re.findall(pattern, content))
        if matches > 0:
            self.stats["replacements"]["Tuple"] += matches
            content = re.sub(pattern, 'tuple[', content)
        return content

    def _replace_set_hints(self, content: str) -> str:
        """Replace Set[X] with set[X]."""
        pattern = r'\bSet\['
        matches = len(re.findall(pattern, content))
        if matches > 0:
            self.stats["replacements"]["Set"] += matches
            content = re.sub(pattern, 'set[', content)
        return content

    def _replace_optional_hints(self, content: str) -> str:
        """Replace Optional[X] with X | None."""
        # This is more complex - need to handle nested types
        pattern = r'\bOptional\[([^\]]+)\]'

        def replace_optional(match):
            inner_type = match.group(1)
            # Handle nested brackets
            bracket_count = inner_type.count('[') - inner_type.count(']')
            if bracket_count != 0:
                # Complex nested type, skip for safety
                return match.group(0)
            self.stats["replacements"]["Optional"] += 1
            return f"{inner_type} | None"

        content = re.sub(pattern, replace_optional, content)
        return content

    def _replace_union_hints(self, content: str) -> str:
        """Replace Union[X, Y] with X | Y."""
        # Simple case: Union[X, Y] → X | Y
        pattern = r'\bUnion\[([^\]]+)\]'

        def replace_union(match):
            inner_types = match.group(1)
            # Split by comma, but be careful with nested types
            if '[' in inner_types and ']' in inner_types:
                # Complex nested type, skip for safety
                return match.group(0)

            # Simple case: split by comma
            types = [t.strip() for t in inner_types.split(',')]
            self.stats["replacements"]["Union"] += 1
            return ' | '.join(types)

        content = re.sub(pattern, replace_union, content)
        return content

    def _update_imports(self, content: str) -> str:
        """Update import statements to remove unnecessary typing imports."""
        lines = content.split('\n')
        new_lines = []
        import_modified = False

        for line in lines:
            # Check if it's a typing import line
            if re.match(r'^from typing import ', line):
                # Remove List, Dict, Tuple, Set, Optional, Union if present
                original_line = line

                # Keep track of what needs to be removed
                to_remove = ['List', 'Dict', 'Tuple', 'Set', 'Optional', 'Union']

                # Parse imports
                import_match = re.match(r'^from typing import (.+)$', line)
                if import_match:
                    imports_str = import_match.group(1)

                    # Handle parenthesized imports
                    if '(' in imports_str:
                        # Multi-line import, skip for safety
                        new_lines.append(line)
                        continue

                    # Split imports
                    imports = [imp.strip() for imp in imports_str.split(',')]

                    # Filter out modernized types
                    remaining = [imp for imp in imports if not any(imp.startswith(rem) for rem in to_remove)]

                    if not remaining:
                        # All imports removed, skip line
                        if self.verbose and not import_modified:
                            print(f"  Removed empty import: {original_line}")
                        import_modified = True
                        continue
                    elif len(remaining) < len(imports):
                        # Some imports removed
                        new_line = f"from typing import {', '.join(remaining)}"
                        new_lines.append(new_line)
                        if self.verbose and not import_modified:
                            print(f"  Updated import: {original_line} → {new_line}")
                        import_modified = True
                        continue

            new_lines.append(line)

        return '\n'.join(new_lines)

    def _show_diff(self, original: str, modified: str, file_path: Path) -> None:
        """Show diff between original and modified content."""
        original_lines = original.split('\n')
        modified_lines = modified.split('\n')

        print(f"\n  Changes in {file_path}:")
        for i, (orig, mod) in enumerate(zip(original_lines, modified_lines), 1):
            if orig != mod:
                print(f"    Line {i}:")
                print(f"      - {orig}")
                print(f"      + {mod}")

    def modernize_directory(self, directory: Path, pattern: str = "**/*.py") -> None:
        """
        Modernize all Python files in directory.

        Args:
            directory: Directory to process
            pattern: Glob pattern for files
        """
        files = list(directory.glob(pattern))
        total_files = len(files)

        print(f"Processing {total_files} files...")

        for file_path in files:
            self.stats["files_processed"] += 1
            self.modernize_file(file_path)

    def print_stats(self) -> None:
        """Print modernization statistics."""
        print("\n" + "=" * 60)
        print("MODERNIZATION STATISTICS")
        print("=" * 60)
        print(f"Files processed: {self.stats['files_processed']}")
        print(f"Files modified: {self.stats['files_modified']}")
        print(f"\nReplacements:")

        total_replacements = sum(self.stats["replacements"].values())
        for type_name, count in self.stats["replacements"].items():
            if count > 0:
                print(f"  {type_name:10s}: {count:4d}")

        print(f"\nTotal replacements: {total_replacements}")
        print("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Modernize Python type hints to 3.10+ syntax"
    )
    parser.add_argument(
        "path",
        type=Path,
        help="File or directory to process"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed progress"
    )
    parser.add_argument(
        "--pattern",
        default="**/*.py",
        help="Glob pattern for files (default: **/*.py)"
    )

    args = parser.parse_args()

    if not args.path.exists():
        print(f"❌ Path does not exist: {args.path}", file=sys.stderr)
        sys.exit(1)

    modernizer = TypeHintModernizer(dry_run=args.dry_run, verbose=args.verbose)

    if args.path.is_file():
        modernizer.modernize_file(args.path)
    else:
        modernizer.modernize_directory(args.path, args.pattern)

    modernizer.print_stats()

    if args.dry_run:
        print("\n💡 Run without --dry-run to apply changes")


if __name__ == "__main__":
    main()
