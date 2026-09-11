"""Audit JSONL responses without imputing structurally absent bearings."""
import argparse
import json
import math
from pathlib import Path


def audit(records):
    seen, last_time = {}, 0.
    counts = {'raw_records': len(records), 'unique_accepted_actions': 0, 'rejected_actions': 0,
              'idempotent_duplicates': 0, 'direction': 0, 'near': 0, 'no_signal': 0,
              'structurally_absent_bearings': 0, 'invalid_records': 0}
    issues, normalized = [], []
    for index, record in enumerate(records):
        req, response, path = record['request'], record['response'], record['path']
        key = req['request_id']
        fingerprint = json.dumps([path, req], sort_keys=True, ensure_ascii=False)
        if key in seen:
            if seen[key] != fingerprint:
                issues.append({'row': index, 'issue': 'same request_id has different payload'})
                counts['invalid_records'] += 1
            else:
                counts['idempotent_duplicates'] += 1
            continue
        seen[key] = fingerprint
        if response.get('accepted') is not True:
            counts['rejected_actions'] += 1
            # Reported zero is a rejection sentinel, not a clock reset.
            continue
        counts['unique_accepted_actions'] += 1
        row = {'path': path, 'virtual_time_s': response['virtual_time_s'], 'svd_deg': None}
        vt = response['virtual_time_s']
        if not isinstance(vt, (int, float)) or not math.isfinite(vt) or vt < last_time - 1e-6:
            issues.append({'row': index, 'issue': 'invalid or decreasing virtual clock'})
            counts['invalid_records'] += 1
        else:
            last_time = vt
        if path in ('/measure', '/clear'):
            ch = req.get('channel')
            p = req.get('position', {})
            valid = isinstance(ch, int) and 1 <= ch <= 20
            valid = valid and all(isinstance(p.get(k), (int, float)) and math.isfinite(p[k]) and abs(p[k]) <= 2e6 for k in ('x', 'y'))
            if not valid:
                issues.append({'row': index, 'issue': 'invalid channel or coordinates'})
                counts['invalid_records'] += 1
            row.update(channel=ch, x=p.get('x'), y=p.get('y'))
        if path == '/measure':
            kind = response.get('measure_result')
            row['measure_result'] = kind
            if kind not in ('direction', 'near', 'no_signal'):
                issues.append({'row': index, 'issue': 'unknown observation branch'})
                counts['invalid_records'] += 1
            else:
                counts[kind] += 1
                if kind == 'direction':
                    bearing = response.get('svd_deg')
                    if not isinstance(bearing, (int, float)) or not math.isfinite(bearing) or not 0 <= bearing < 360:
                        issues.append({'row': index, 'issue': 'direction response lacks a valid bearing'})
                        counts['invalid_records'] += 1
                    else:
                        row['svd_deg'] = bearing
                else:
                    counts['structurally_absent_bearings'] += 1
        normalized.append(row)
    return {'counts': counts, 'issues': issues, 'last_accepted_virtual_time_s': last_time, 'normalized': normalized}


def main():
    """Audit a JSONL action log from the command line."""
    parser = argparse.ArgumentParser()
    parser.add_argument('jsonl')
    parser.add_argument('--output', default='audit.json')
    args = parser.parse_args()
    records = [json.loads(s) for s in Path(args.jsonl).read_text(encoding='utf-8-sig').splitlines() if s.strip()]
    result = audit(records)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result['counts'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
