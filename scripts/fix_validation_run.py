#!/usr/bin/env python3
"""
Script to fix ValidationRun instantiations by adding required fields.
Adds trigger_type, data_start_date, data_end_date to all ValidationRun calls.
"""

from pathlib import Path


def fix_imports(content: str) -> str:
    """Add required imports if missing."""
    lines = content.split("\n")
    new_lines = []
    datetime_import_fixed = False
    validation_run_import_fixed = False

    for line in lines:
        # Fix datetime import to include timedelta
        if "from datetime import" in line and "timedelta" not in line and not datetime_import_fixed:
            # Add timedelta to the import
            if line.strip().endswith(","):
                # Multi-line import
                new_lines.append(line)
            else:
                # Single line import - add timedelta
                parts = line.split("import")
                imports = parts[1].strip()
                if "date" in imports and "datetime" in imports:
                    # Already has both date and datetime
                    line = f"{parts[0]}import {imports}, timedelta"
                else:
                    line = f"{parts[0]}import {imports}, timedelta"
                new_lines.append(line)
                datetime_import_fixed = True
        # Fix validation_run import to include TriggerType
        elif (
            "from src.models.validation_run import" in line
            and "TriggerType" not in line
            and not validation_run_import_fixed
        ):
            # Add TriggerType to the import
            parts = line.split("import")
            imports = parts[1].strip()
            line = f"{parts[0]}import TriggerType, {imports}"
            new_lines.append(line)
            validation_run_import_fixed = True
        else:
            new_lines.append(line)

    return "\n".join(new_lines)


def fix_validation_run(content: str) -> str:
    """Add required fields to ValidationRun instantiations."""
    lines = content.split("\n")
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this line contains started_at=datetime.utcnow()
        if "started_at=datetime.utcnow()" in line:
            # Check if we already have trigger_type nearby (within 10 lines up)
            has_trigger_type = any("trigger_type=" in lines[max(0, i - j)] for j in range(10))

            if not has_trigger_type:
                # Add the required fields before started_at
                indent = " " * (len(line) - len(line.lstrip()))

                # Add trigger_type line before current line
                new_lines.append(f"{indent}trigger_type=TriggerType.MANUAL,")

                # Add current started_at line (ensure it has comma)
                if line.rstrip().endswith(","):
                    new_lines.append(line)
                else:
                    new_lines.append(line.rstrip() + ",")

                # Add data_start_date and data_end_date
                new_lines.append(f"{indent}data_start_date=date.today() - timedelta(days=30),")
                new_lines.append(f"{indent}data_end_date=date.today(),")

                i += 1
                continue

        new_lines.append(line)
        i += 1

    return "\n".join(new_lines)


def main():
    """Fix all test files in tests/validation/."""
    test_dir = Path("tests/validation")

    for test_file in sorted(test_dir.glob("test_*.py")):
        print(f"Processing {test_file}...")

        content = test_file.read_text()

        # Skip if no ValidationRun
        if "ValidationRun(" not in content:
            print("  Skipped (no ValidationRun)")
            continue

        # Fix imports
        content = fix_imports(content)

        # Fix ValidationRun instantiations
        content = fix_validation_run(content)

        # Write back
        test_file.write_text(content)
        print("  Fixed!")


if __name__ == "__main__":
    main()
