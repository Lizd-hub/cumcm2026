"""Run an offline example, or explicitly connect to a user-started simulator."""
import argparse
import json
from pathlib import Path
import time
from .offline_simulator import OfflineSimulator
from .protocol import Session, HTTPTransport
from .solver import Solver


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--question', type=int, choices=[3, 4], default=3)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--output', default='run_output')
    parser.add_argument('--connect', action='store_true', help='Connect to the locally running official simulator')
    parser.add_argument('--team-id', default='')
    parser.add_argument('--base-url', default='http://127.0.0.1:32026')
    parser.add_argument('--session-kind', choices=['practice', 'formal'])
    parser.add_argument('--ack-session-start', action='store_true', help='You checked the UI and authorize entering this active session')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if args.connect:
        if not (args.team_id and args.session_kind and args.ack_session_start):
            parser.error('Connection requires --team-id, --session-kind and --ack-session-start. Check the simulator UI first.')
        print('The API does not identify practice/formal mode. Your UI selection is authoritative.')
        if args.session_kind == 'formal':
            print('This command will enter the active FORMAL session; it may consume a limited official attempt.')
        transport = HTTPTransport(args.base_url)
        name = f'q{args.question}_{args.session_kind}_{time.time_ns()}'
        session = Session(transport, args.team_id, output / (name + '.jsonl'))
    else:
        transport = OfflineSimulator(args.seed, mixed=args.question == 4)
        name = f'local_q{args.question}_seed{args.seed}_{time.time_ns()}'
        session = Session(transport, log_path=output / (name + '.jsonl'))
    solver = Solver(session, mixed=args.question == 4, improved=not args.baseline)
    start = time.perf_counter()
    try:
        result = solver.run()
        result['client_wall_time_s'] = time.perf_counter() - start
        result['result_origin'] = 'official_interface_unverified_ui_mode' if args.connect else 'independent_local_emulator'
        if not args.connect:
            result.update(transport.evaluate())
            result['local_sources'] = transport.export_truth_for_local_plot()
            result['path'] = transport.path
    except Exception as exc:
        result = {'completed': False, 'error': str(exc), 'virtual_time_s': session.virtual_time,
                  'cleared': len(solver.cleared), 'client_wall_time_s': time.perf_counter() - start}
        if session.started:
            try:
                session.exit()
            except Exception as exit_error:
                result['exit_error'] = str(exit_error)
        (output / (name + '_failure.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        raise
    (output / (name + '_summary.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('path', 'local_sources')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
