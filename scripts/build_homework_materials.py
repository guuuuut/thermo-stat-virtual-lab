"""Build the public six-choice assignment page and deterministic student archive."""
from __future__ import annotations

import hashlib
import html
import json
import re
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_SOURCE = PROJECT_ROOT / 'results/homework_20261027/student_data'
ASSIGNMENT = PROJECT_ROOT / 'docs/homework_20261027.md'
README = PROJECT_ROOT / 'downloads/README_homework.md'
TEMPLATE = PROJECT_ROOT / 'visualization/homework_template.html'
PAGE = PROJECT_ROOT / 'visualization/homework.html'
ARCHIVE = PROJECT_ROOT / 'downloads/homework_20261027.zip'
ARCHIVE_ROOT = '六选一作业数据/'
PAGE_MARKER = '<meta name="visual-lab-page" content="homework-six-choice-v1">'
EXPECTED_FILES = 67
QUESTIONS = {
    'Q1_speed_distribution', 'Q2_pressure', 'Q3_boundaries',
    'Q4_temperature_diffusion', 'Q5_system_size', 'Q6_velocity_correlation',
}


def inline_markdown(text: str) -> str:
    """Render the deliberately small inline vocabulary used by our source sheet."""
    text = html.escape(text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    return re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)


def assignment_html(source: str) -> str:
    blocks: list[str] = []
    paragraph: list[str] = []
    in_list = False

    def flush() -> None:
        if paragraph:
            blocks.append('<p>' + inline_markdown(' '.join(paragraph)) + '</p>')
            paragraph.clear()

    for line in source.splitlines():
        line = line.strip()
        if not line:
            flush()
            if in_list:
                blocks.append('</ul>')
                in_list = False
        elif line.startswith('#'):
            flush()
            if in_list:
                blocks.append('</ul>')
                in_list = False
            heading = re.fullmatch(r'(#{1,2}) (.+)', line)
            if not heading:
                raise ValueError(f'Unsupported assignment heading: {line}')
            level = len(heading[1])
            blocks.append(f'<h{level}>{inline_markdown(heading[2])}</h{level}>')
        elif line.startswith('- '):
            flush()
            if not in_list:
                blocks.append('<ul>')
                in_list = True
            blocks.append('<li>' + inline_markdown(line[2:]) + '</li>')
        else:
            paragraph.append(line)
    flush()
    if in_list:
        blocks.append('</ul>')
    return '\n'.join(blocks)


def student_files() -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for path in sorted(DATA_SOURCE.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(DATA_SOURCE)
        if rel.as_posix() != 'dataset_metadata.json':
            if rel.parts[0] not in QUESTIONS or path.suffix not in {'.csv', '.json'}:
                raise ValueError(f'Unexpected student source: {rel}')
        files[rel.as_posix()] = path.read_bytes()
    if {name.split('/')[0] for name in files if '/' in name} != QUESTIONS:
        raise ValueError('The student sources must cover all six questions.')
    metadata = json.loads(files['dataset_metadata.json'])
    if metadata['source_cases'] != 47 or metadata['questions'] != 6:
        raise ValueError('Unexpected dataset metadata.')
    files['作业题目_六选一.md'] = ASSIGNMENT.read_bytes()
    files['数据说明.md'] = README.read_bytes()
    hashes = [hashlib.sha256(body).hexdigest() + '  ' + name for name, body in sorted(files.items())]
    files['SHA256SUMS.txt'] = ('\n'.join(hashes) + '\n').encode('utf-8')
    if len(files) != EXPECTED_FILES:
        raise ValueError(f'Student archive must contain {EXPECTED_FILES} files; got {len(files)}.')
    return files


def verify_archive(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError('Student archive failed its CRC check.')
        names = archive.namelist()
        if len(names) != EXPECTED_FILES or len(names) != len(set(names)):
            raise ValueError('Unexpected archive member count or duplicate names.')
        for name in names:
            if not name.startswith(ARCHIVE_ROOT) or '..' in Path(name).parts or '\\' in name:
                raise ValueError(f'Unsafe archive member: {name}')
            if Path(name).suffix not in {'.csv', '.json', '.md', '.txt'}:
                raise ValueError(f'Non-student material in archive: {name}')
        checks = archive.read(ARCHIVE_ROOT + 'SHA256SUMS.txt').decode('utf-8').splitlines()
        if len(checks) != EXPECTED_FILES - 1:
            raise ValueError('The archive hash manifest is incomplete.')
        for check in checks:
            digest, name = check.split('  ', 1)
            if hashlib.sha256(archive.read(ARCHIVE_ROOT + name)).hexdigest() != digest:
                raise ValueError(f'Student file hash mismatch: {name}')


def main() -> None:
    files = student_files()
    ARCHIVE.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, body in sorted(files.items()):
            info = zipfile.ZipInfo(ARCHIVE_ROOT + name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, body)
    verify_archive(ARCHIVE)
    source = ASSIGNMENT.read_text(encoding='utf-8')
    template = TEMPLATE.read_text(encoding='utf-8')
    if template.count('__ASSIGNMENT_CONTENT__') != 1 or PAGE_MARKER not in template:
        raise ValueError('Homework template marker or content placeholder is missing.')
    page = template.replace('__ASSIGNMENT_CONTENT__', assignment_html(source))
    page = page.replace('__ARCHIVE_SIZE_MB__', f'{ARCHIVE.stat().st_size / 1_000_000:.1f}')
    PAGE.write_text(page, encoding='utf-8')
    print(f'Built {PAGE.name} and {ARCHIVE.name}: {len(files)} verified student files.')


if __name__ == '__main__':
    main()
