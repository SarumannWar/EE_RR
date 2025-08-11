#!/usr/bin/env python3
import json, os, sys
from argparse import ArgumentParser

# Asegurar imports desde la carpeta scripts
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts'))
if SCRIPTS_DIR not in sys.path:
    sys.path.append(SCRIPTS_DIR)

from generate_eerr_excel import build_pivot, REPORT_STRUCTURE, SPANISH_MONTHS
from generate_eerr_with_breakdowns import build_pivot_by_group, load_responsables_table


def build_months_by_year(months):
    years = sorted({y for (y, m) in months})
    months_by_year = {y: [m for (yy, m) in months if yy == y] for y in years}
    labels_by_year = {y: [f"{SPANISH_MONTHS[m]}" for m in months_by_year[y]] for y in years}
    return years, months_by_year, labels_by_year


def rows_from_per_row(months_by_year, per_row):
    # Retorna filas con valores por año como listas alineadas al orden de months_by_year[y]
    rows = []
    for name, level in REPORT_STRUCTURE:
        values_by_year = {}
        for y, mlist in months_by_year.items():
            values_by_year[str(y)] = [per_row.get(name, {}).get((y, m), 0.0) for m in mlist]
        rows.append({
            'Cuenta': name,
            'level': level,
            'bold': name.startswith('Total ') or name in ('Utilidad', 'Resultado antes de impuesto'),
            'values_by_year': values_by_year,
        })
    return rows


def build_dataset(csv_path, delimiter, responsables_xlsx):
    # EERR base
    months, per_row = build_pivot(csv_path, delimiter)
    years, months_by_year, labels_by_year = build_months_by_year(months)

    data = {
        'years': years,
        'months_by_year': months_by_year,
        'labels_by_year': labels_by_year,
        'sheets': {}
    }

    # EERR (Global)
    data['sheets']['EERR'] = {
        'groups': [
            {'name': 'Global', 'rows': rows_from_per_row(months_by_year, per_row)}
        ]
    }

    # Breakdown por Responsable/Broker/Tipo
    mapping = load_responsables_table(responsables_xlsx)
    def mapper(kind):
        return lambda row: mapping.get((row.get('Proyecto') or '').strip(), {}).get(kind) or f'Sin {kind}'

    for kind, title in [('Responsable', 'EERR_por_Responsable'), ('Broker', 'EERR_por_Broker'), ('Tipo', 'EERR_por_Tipo')]:
        _months, groups, per_group = build_pivot_by_group(csv_path, delimiter, mapper(kind))
        # Usar months_by_year del EERR base para mantener alineación
        group_list = []
        for g in sorted(groups):
            per_row_g = per_group[g]
            rows_g = rows_from_per_row(months_by_year, per_row_g)
            group_list.append({'name': g, 'rows': rows_g})
        data['sheets'][title] = {'groups': group_list}

    return data


def main():
    ap = ArgumentParser(description='Exporta JSON simple para dashboard v2 (solo meses)')
    ap.add_argument('--csv', required=True)
    ap.add_argument('--delimiter', default=';')
    ap.add_argument('--responsables', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--also_js', action='store_true', help='Si se indica, además genera data.js con variable global DASHBOARD_DATA')
    args = ap.parse_args()

    data = build_dataset(args.csv, args.delimiter, args.responsables)
    out_dir = os.path.dirname(args.output)
    os.makedirs(out_dir, exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    print(f'Export OK: {args.output}')
    if args.also_js:
        js_path = os.path.join(out_dir, 'data.js')
        with open(js_path, 'w', encoding='utf-8') as f:
            f.write('window.DASHBOARD_DATA = ')
            json.dump(data, f, ensure_ascii=False)
            f.write(';')
        print(f'Export OK: {js_path}')


if __name__ == '__main__':
    main()

