#!/usr/bin/env python3
import argparse
import json
import os
import pathlib
import sys

import pandas as pd


def parse_ipynb(path):
    import json
    with open(path, 'r', encoding='utf-8') as f:
        notebook = json.load(f)
    cells = notebook.get('cells', [])
    source_lines = []
    for cell in cells:
        if cell.get('cell_type') != 'code':
            continue
        cell_source = cell.get('source', [])
        if isinstance(cell_source, list):
            source_lines.extend(cell_source)
            source_lines.append('\n')
        else:
            source_lines.append(cell_source)
            source_lines.append('\n')
    return ''.join(source_lines)


def execute_source(source, path):
    namespace = {
        '__name__': '__main__',
        '__file__': path,
    }
    exec(compile(source, path, 'exec'), namespace)
    return namespace


def serialize_dataframe(df):
    if not isinstance(df, pd.DataFrame):
        raise TypeError('Expected a pandas DataFrame')
    return json.loads(df.to_json(orient='records'))


def extract_results(namespace):
    candidates = [
        ('evaluation_df', namespace.get('evaluation_df')),
        ('generations_df', namespace.get('generations_df')),
        ('generation_rows', namespace.get('generation_rows')),
        ('evaluation_rows', namespace.get('evaluation_rows')),
        ('results', namespace.get('results')),
        ('data', namespace.get('data')),
    ]
    for name, value in candidates:
        if value is None:
            continue
        if isinstance(value, pd.DataFrame):
            return serialize_dataframe(value)
        if isinstance(value, list):
            return value
        if isinstance(value, dict) and 'entries' in value and isinstance(value['entries'], list):
            return value['entries']
    raise ValueError(
        'No usable evaluation object found. Expected one of: evaluation_df, generations_df, generation_rows, evaluation_rows, results with entries, or a list.'
    )


def main():
    parser = argparse.ArgumentParser(
        description='Extract evaluation results from a notebook or Python script into dashboard JSON.'
    )
    parser.add_argument('input', help='Path to .py or .ipynb file')
    parser.add_argument('--output', '-o', default='results.json', help='Output JSON path')
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    if not path.exists():
        print(f'Error: file not found: {path}', file=sys.stderr)
        sys.exit(1)

    if path.suffix == '.ipynb':
        source = parse_ipynb(path)
    elif path.suffix == '.py':
        source = path.read_text(encoding='utf-8')
    else:
        print('Error: input must be .py or .ipynb', file=sys.stderr)
        sys.exit(1)

    namespace = execute_source(source, str(path))
    try:
        entries = extract_results(namespace)
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        available = ', '.join(sorted(namespace.keys()))
        print(f'Available variables: {available}', file=sys.stderr)
        sys.exit(1)

    out_path = pathlib.Path(args.output)
    out_path.write_text(json.dumps({'entries': entries}, indent=2), encoding='utf-8')
    print(f'Wrote {out_path.resolve()}')


if __name__ == '__main__':
    main()
