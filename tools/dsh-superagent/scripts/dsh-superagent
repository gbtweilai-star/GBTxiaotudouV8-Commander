#!/usr/bin/env python3
"""Manage a local dsh-superagent service (one DSH profile, default `superagent`) without affecting other tmux sessions.

`status`, `start`, and `restart` exit 0 while the service runs normally; 1 when it is stopped, duplicated, unreachable, or
reporting a runtime error, which `restart` may fix; 2 when it runs while a component such as a Source reports an error;
and 3 when it runs and waits for setup. A restart fixes neither 2 nor 3: they need a person.
"""

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / '.artifacts'
CONTROL = ARTIFACTS / 'control'
KEEP_LOGS = 20


def control(profile):
    """Return the control directory for `profile`, creating it if needed."""
    directory = CONTROL / 'profiles' / profile
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def stopped(profile):
    """Return whether `profile` was intentionally stopped."""
    return (control(profile) / 'manually-stopped').exists()


def serves(args, profile):
    """Return whether command-line arguments belong to the main DSH service process for `profile`."""
    words, matched, value = [], False, False
    for word in args[1:]:
        if value:
            matched, value = matched or word == profile, False
        elif word == '--profile':
            value = True
        elif word == '--profile=' + profile:
            matched = True
        elif not word.startswith('-'):
            words.append(word)
    return matched and 'plugin' not in words


def ps(*options, check=False):
    """Yield `(pid, comm, args)` tuples from `ps`; arguments are split on whitespace, so paths with spaces become several words and only `--profile` and subcommands are inspected."""
    result = subprocess.run(['ps', '-ww', *options, '-o', 'pid=,ucomm=,args='], check=check, capture_output=True, text=True)
    for line in result.stdout.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[0].isdigit():
            yield int(parts[0]), parts[1], parts[2].split()


def running(pid, profile):
    """Return whether `pid` is currently running the DSH service for `profile` (`ps -p` returns nothing once exited)."""
    return any(found == pid and name in ('node', 'dsh') and serves(args, profile) for found, name, args in ps('-p', str(pid)))


def processes(profile):
    """Return PIDs of all running DSH service processes for `profile`, including instances started outside this script and the recorded `service.pid` while still running."""
    found = [pid for pid, name, args in ps('-ax', check=True) if name in ('node', 'dsh') and serves(args, profile)]
    try:
        pid = int((control(profile) / 'service.pid').read_text())
    except (OSError, ValueError):
        return found
    return found + [pid] if pid not in found and running(pid, profile) else found


def state(url):
    """Fetch health and setup status from the management API, or return None if unreachable."""
    request = urllib.request.Request(url.rstrip('/') + '/orchestrator/api/state',
                                     headers={'x-orchestrator-request': '1'})
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            value = json.load(response)
        # Keys omitted by another version read as empty so the service is not mistaken for unreachable.
        health, setup = value.get('health') or {}, value.get('setup') or {}
        entries = {name: entry if isinstance(entry, dict) else {} for name, entry in health.items()}
        return {'health': {name: entry.get('state') for name, entry in entries.items()},
                'errors': {name: str(entry.get('detail', '')) for name, entry in entries.items() if entry.get('state') == 'error'},
                'setup': setup.get('problem'), 'feishu': setup.get('feishuProblem')}
    except (OSError, ValueError, AttributeError):
        return None


PART_ERROR = 2
SETUP_WAITS = 3


def runtime_up(current):
    """Return whether the runtime is ready or paused awaiting operator action; a component still starting (such as history recovery) does not hold this up."""
    return current is not None and current['health'].get('runtime') in ('ready', 'paused')


def part_errors(current):
    """Return non-runtime components that are in an error state."""
    return {name: detail for name, detail in sorted(current['errors'].items()) if name != 'runtime'}


def outcome(pids, current):
    """Compute the CLI exit code from running PIDs and management API state."""
    if len(pids) != 1 or not runtime_up(current):
        return 1
    if current['setup']:
        return SETUP_WAITS
    # A component's lasting error, unlike a Feishu bot check that failed during setup, requires operator action.
    return PART_ERROR if part_errors(current) else 0


def status(args):
    pids = processes(args.profile)
    current = state(args.url) if pids else None
    print(json.dumps({'pids': pids, 'cwd': str(ROOT), 'url': args.url,
                      'manually_stopped': stopped(args.profile), 'health': current and current['health'],
                      'errors': current and current['errors'], 'setup': current and current['setup'],
                      'feishu': current and current['feishu']}, ensure_ascii=False, indent=2))
    return outcome(pids, current)


def stop(args, intentional=True):
    """Stop the service gracefully, recording a manual stop marker when `intentional` is True."""
    pids = processes(args.profile)
    if len(pids) > 1:
        raise RuntimeError('Multiple dsh-superagent processes found; refusing to choose one.')
    # Write the stop marker before waiting so monitors respect the intentional stop even if graceful shutdown times out.
    if intentional:
        (control(args.profile) / 'manually-stopped').write_text(time.strftime('%Y-%m-%dT%H:%M:%S%z') + '\n')
    for pid in pids:
        os.kill(pid, signal.SIGINT)
    deadline = time.monotonic() + args.stop_timeout
    while any(running(pid, args.profile) for pid in pids):
        if time.monotonic() >= deadline:
            raise RuntimeError('Graceful stop timed out; no forced kill was sent. Check status.')
        time.sleep(0.5)
    (control(args.profile) / 'service.pid').unlink(missing_ok=True)
    print('dsh-superagent stopped. Automatic recovery is paused until start/restart.' if intentional else 'dsh-superagent stopped.')


def prune_logs(profile):
    """Retain only the newest `KEEP_LOGS` log files for `profile`."""
    name = re.compile(re.escape(f'dsh-superagent-{profile}-') + r'\d{8}-\d{6}-\d+\.log')
    logs = sorted((path for path in ARTIFACTS.iterdir() if name.fullmatch(path.name)), key=lambda path: path.stat().st_mtime)
    for path in logs[:-KEEP_LOGS]:
        path.unlink(missing_ok=True)


def start(args):
    session = 'dsh-' + args.profile
    pids = processes(args.profile)
    if len(pids) > 1:
        raise RuntimeError('Multiple dsh-superagent processes found; refusing to start another.')
    if not pids:
        dsh = shutil.which('dsh')
        if not dsh or not shutil.which('tmux'):
            raise RuntimeError('Both dsh and tmux must be on PATH.')
        exists = subprocess.run(['tmux', 'has-session', '-t', '=' + session],
                                capture_output=True).returncode == 0
        if state(args.url) is not None:
            raise RuntimeError('An existing orchestrator answers at this URL; refusing duplicate startup.')
        stamp = time.strftime('%Y%m%d-%H%M%S')
        log = ARTIFACTS / f'dsh-superagent-{args.profile}-{stamp}-{os.getpid()}.log'
        log.touch()
        prune_logs(args.profile)
        # `exec` replaces the shell so the pane PID printed by tmux is the DSH service process itself.
        command = ('umask 077; exec ' + shlex.join([dsh, '--profile', args.profile, '--no-open'])
                   + ' >> ' + shlex.quote(str(log)) + ' 2>&1')
        # Reuse an existing tmux session without disturbing other windows.
        target = ['new-window', '-t', '=' + session + ':'] if exists else ['new-session', '-s', session]
        pane = subprocess.run(['tmux', *target, '-d', '-P', '-F', '#{pane_pid}', '-n', 'server', '-c', str(ROOT), command],
                              check=True, capture_output=True, text=True).stdout.strip()
        if pane.isdigit():
            (control(args.profile) / 'service.pid').write_text(pane + '\n')
        print('Log: ' + str(log), flush=True)
    else:
        (control(args.profile) / 'service.pid').write_text(f'{pids[0]}\n')
        print(f'dsh-superagent already running (PID {pids[0]}); no duplicate started.', flush=True)
    (control(args.profile) / 'manually-stopped').unlink(missing_ok=True)
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        current = state(args.url)
        if processes(args.profile) and runtime_up(current):
            code = status(args)
            if current['setup']:
                print('dsh-superagent is waiting for setup: ' + str(current['setup'].get('detail', '')))
                print('Open the URL DSH printed in the log, then the dsh-superagent overview.')
            if current['feishu']:
                print('dsh-superagent runs without Feishu: ' + str(current['feishu'].get('detail', '')))
                print('Fix it on the Feishu card of the Source settings.')
            for name, detail in part_errors(current).items():
                print(f'{name} reports an error, which a restart does not fix: {detail}')
            return code
        time.sleep(1)
    status(args)
    raise RuntimeError('Startup health check timed out; inspect the log. Any running process was left intact.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop', 'restart', 'status'])
    parser.add_argument('--profile', default=os.environ.get('DSH_SUPERAGENT_PROFILE') or 'superagent',
                        help='DSH profile that loads dsh-superagent; its tmux session is dsh-<profile>.')
    parser.add_argument('--url', default=os.environ.get('DSH_SUPERAGENT_URL') or 'http://127.0.0.1:3082',
                        help='Health-check URL; override after changing the profile port.')
    parser.add_argument('--timeout', type=float, default=60, help='Startup timeout in seconds.')
    parser.add_argument('--stop-timeout', type=float, default=300,
                        help='Graceful shutdown timeout in seconds; running Executor Sessions finish their step first.')
    parser.add_argument('--respect-stop', action='store_true',
                        help='For monitoring: never start/restart after an intentional stop.')
    args = parser.parse_args()
    if args.timeout <= 0 or args.stop_timeout <= 0:
        parser.error('--timeout and --stop-timeout must be positive')
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', args.profile):
        parser.error('--profile must be a DSH profile name')
    os.umask(0o077)
    with (control(args.profile) / 'operation.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another dsh-superagent control operation is in progress.') from None
        if args.respect_stop and args.action in ('start', 'restart') and stopped(args.profile):
            print('Intentional stop is active; automatic recovery skipped.')
            return 0
        if args.action == 'status':
            return status(args)
        if args.action in ('stop', 'restart'):
            # Only a stop keeps automatic recovery off; a restart whose stop timed out leaves it on.
            stop(args, intentional=args.action == 'stop')
        if args.action in ('start', 'restart'):
            return start(args)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
