"""Regenerate selectable-text fixtures locally; no application/service imports."""
import json
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent


def generate(output_dir=ROOT):
    """Stable content/layout; omit random PDF IDs and time-dependent metadata."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    source = json.loads((ROOT / 'syllabi.json').read_text(encoding='utf-8'))
    for fixture in source['documents']:
        with pymupdf.open() as document:
            document.set_metadata({'title': fixture['id'] + ' fictional syllabus',
                                   'author': 'Silly Billy test fixtures'})
            for lines in fixture['pages']:
                page = document.new_page(width=612, height=792)
                if lines:
                    remaining = page.insert_textbox(
                        pymupdf.Rect(48, 48, 564, 744), '\n\n'.join(lines),
                        fontsize=12, fontname='helv', lineheight=1.2,
                    )
                    if remaining < 0:
                        raise ValueError('Fixture text exceeds one physical page')
            document.save(output_dir / fixture['pdf'], garbage=4, deflate=True,
                          no_new_id=True)


if __name__ == '__main__':
    generate()
