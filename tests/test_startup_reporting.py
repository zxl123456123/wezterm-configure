"""Real PS/CMD hosts with guarded, test-only substitutions; never run the launcher."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

TEST_DIR = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--source-dir', type=Path, default=TEST_DIR.parent)
args, unittest_args = parser.parse_known_args()
SOURCE = args.source_dir.resolve()
PS_SOURCE = (SOURCE / 'Ensure-WorkbenchTabs.ps1').read_text(encoding='utf-8-sig')
CMD_SOURCE = (SOURCE / 'Start-TerminalWorkbench.cmd').read_text(encoding='utf-8-sig')
EXPRESSION = '[System.Diagnostics.Process]::Start($info)'
PREFIX = (TEST_DIR / 'startup_fake_process.ps1').read_text(encoding='utf-8-sig')


def guarded_ps_fixture(source):
    if source.count(EXPRESSION) != 1:
        raise ValueError('Expected exactly one production Process.Start expression')
    replaced = source.replace(EXPRESSION, '(New-StartupFakeProcess $info)')
    if re.search(r'\[System\.Diagnostics\.Process\]\s*::\s*Start', replaced, re.I):
        raise ValueError('A real Process.Start remains')
    if not re.search(r'function Start-Sleep\s*\{', PREFIX):
        raise ValueError('Sleep mock missing')
    if 'function New-StartupFakeProcess' not in PREFIX or 'param([int]$Milliseconds)' not in PREFIX:
        raise ValueError('Fake factory guard missing')
    # Known production command surface only: functions plus script main, no shell launches.
    if re.search(r'(?im)^\s*(?:Start-Process|&\s|cmd(?:\.exe)?\s|powershell\s)', replaced):
        raise ValueError('Unexpected external execution surface')
    return PREFIX + '\n' + replaced


def guarded_cmd_fixture(source, code, branch, log):
    lines = source.splitlines()
    block_start = lines.index('if not errorlevel 1 (')
    block_end = lines.index(')', block_start)
    calls = [i for i, line in enumerate(lines)
             if line.lstrip().startswith('powershell -NoProfile -ExecutionPolicy Bypass -File ')
             and 'Ensure-WorkbenchTabs.ps1' in line]
    if len(calls) != 2 or not block_start < calls[0] < block_end or calls[1] <= block_end:
        raise ValueError('Expected the two launcher Ensure anchors')
    retained = ['@echo off', f'cmd /d /c exit {0 if branch == "existing" else 1}', lines[block_start]]
    for i in range(calls[0], block_end + 1):
        retained.append(f'  cmd /d /c exit {code} >> "{log}" 2>&1' if i == calls[0] else lines[i])
    for i in range(calls[1], len(lines)):
        retained.append(f'cmd /d /c exit {code} >> "{log}" 2>&1' if i == calls[1] else lines[i])
    # No GUI/CIM/start/env commands survive extraction; whitelist every retained line.
    allowed = re.compile(r'^(?:@echo off|cmd /d /c exit \d+(?: >> ".+" 2>&1)?|'
                         r'if not errorlevel 1 \(|\)|if errorlevel 1 goto startup_failed|'
                         r'exit /b (?:0|%workbench_startup_exit%)|:startup_failed|'
                         r'set "workbench_startup_exit=%errorlevel%"|'
                         r'echo Workbench startup failed: exit=%workbench_startup_exit%\. '
                         r'See D:\\terminal-workbench\\data\\startup\.log 1>&2|'
                         r'>> "D:\\terminal-workbench\\data\\startup\.log" '
                         r'echo Workbench startup failed: exit=%workbench_startup_exit%\.)$', re.I)
    for line in retained:
        if not line.strip():
            continue
        if not allowed.fullmatch(line.strip()):
            raise ValueError(f'Unsafe/unrecognized CMD fixture line: {line}')
    if any(re.match(r'\s*(?:pause|wezterm\S*)(?:\s|$)', line, re.I) for line in retained):
        raise ValueError('Interactive/live command in fixture')
    # Only redirect the known persistent log; error summary still names production log.
    fixture = '\n'.join(retained) + '\n'
    fixture = fixture.replace('>> "D:\\terminal-workbench\\data\\startup.log"', f'>> "{log}"')
    return fixture


class StartupTests(unittest.TestCase):
    def run_ps(self, scenario):
        fixture = guarded_ps_fixture(PS_SOURCE)
        with tempfile.TemporaryDirectory(prefix='startup-ps-', dir=TEST_DIR) as temp:
            script = Path(temp) / 'startup-isolated.ps1'
            script.write_text(fixture, encoding='utf-8-sig')
            env = os.environ.copy()
            env['STARTUP_TEST_SCENARIO'] = scenario
            run = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                                  '-File', str(script)], env=env, capture_output=True,
                                 text=True, encoding='utf-8', errors='replace', timeout=15)
        trace, diagnostics = [], []
        for line in run.stderr.splitlines():
            if line.startswith('@@TRACE@@'):
                trace.append(json.loads(line[len('@@TRACE@@'):]))
            else:
                diagnostics.append(line)
        print(f'PS {scenario} exit={run.returncode} stdout={run.stdout!r} '
              f'diagnostic={chr(10).join(diagnostics)!r} trace={json.dumps(trace)}')
        self.assertTrue(trace, 'Fake process was not invoked')
        starts = sum(x['type'] == 'start' for x in trace)
        disposed = sum(x['type'] == 'dispose' for x in trace)
        if scenario != 'startfail':
            self.assertEqual(starts, disposed)
        return run.returncode, '\n'.join(diagnostics), trace

    def test_ready_and_recovery(self):
        for scenario, expected_lists, expected_sleeps in [('ready', 1, 0), ('recovery', 3, 2)]:
            with self.subTest(scenario=scenario):
                code, diagnostic, trace = self.run_ps(scenario)
                self.assertEqual(code, 0)
                self.assertEqual(diagnostic, '')
                starts = [x for x in trace if x['type'] == 'start']
                self.assertEqual([x['action'] for x in starts], ['list-tabs'] * expected_lists + ['go-to-tab'])
                self.assertTrue(starts[-1]['arguments'].endswith('"go-to-tab" "2"'))
                self.assertEqual(sum(x['type'] == 'sleep' for x in trace), expected_sleeps)

    def test_missing_tab_success(self):
        code, diagnostic, trace = self.run_ps('missing')
        self.assertEqual((code, diagnostic), (0, ''))
        starts = [x for x in trace if x['type'] == 'start']
        self.assertEqual([x['action'] for x in starts],
                         ['list-tabs', 'new-tab', 'list-tabs', 'move-tab', 'move-tab',
                          'move-tab', 'list-tabs', 'go-to-tab'])
        self.assertIn('"--name" "Monitor"', starts[1]['arguments'])
        self.assertIn('"--tab-id" "15" "left"', starts[3]['arguments'])
        self.assertTrue(starts[-1]['arguments'].endswith('"go-to-tab" "2"'))
        self.assertEqual([x['timeout'] for x in trace if x['type'] == 'wait'],
                         [2000, 8000, 2000, 2000, 2000, 2000, 2000, 2000])

    def test_readiness_failure_context(self):
        for scenario in ['nativefail', 'empty', 'unparsed', 'startfail', 'timeout']:
            with self.subTest(scenario=scenario):
                code, diagnostic, trace = self.run_ps(scenario)
                self.assertEqual(code, 1)
                self.assertEqual(sum(x['type'] == 'start' for x in trace), 20)
                self.assertEqual([x['milliseconds'] for x in trace if x['type'] == 'sleep'], [400] * 20)
                self.assertIn('workbench-v4', diagnostic)
                self.assertIn('wait-session', diagnostic)
                self.assertIn('20 attempts', diagnostic)
                self.assertIn('list-tabs', diagnostic)
                if scenario == 'nativefail':
                    for part in ['exit=7', 'stdout:', 'stderr:', 'ready-out-20', 'ready-error-20']:
                        self.assertIn(part, diagnostic)
                elif scenario in ['empty', 'unparsed']:
                    self.assertIn('no parseable tabs', diagnostic)
                elif scenario == 'startfail':
                    self.assertIn('fake start failure', diagnostic)
                elif scenario == 'timeout':
                    self.assertIn('2000ms', diagnostic)
                    self.assertEqual(sum(x['type'] == 'kill' for x in trace), 20)

    def test_action_failures_stop_and_report(self):
        for scenario, stage, action in [('newfail', 'create Monitor', 'new-tab'),
                                       ('movefail', 'move Monitor', 'move-tab'),
                                       ('restorefail', 'restore Work-for-Linux', 'go-to-tab'),
                                       ('create-timeout', 'create Monitor', 'new-tab')]:
            with self.subTest(scenario=scenario):
                code, diagnostic, trace = self.run_ps(scenario)
                self.assertEqual(code, 1)
                self.assertIn(stage, diagnostic)
                self.assertIn(action, diagnostic)
                self.assertIn('workbench-v4', diagnostic)
                self.assertEqual([x['action'] for x in trace if x['type'] == 'start'][-1], action)
                if scenario == 'create-timeout':
                    self.assertIn('8000ms', diagnostic)
                    self.assertEqual(sum(x['type'] == 'kill' for x in trace), 1)
                else:
                    for part in ['exit=7', 'action-out', 'action-error']:
                        self.assertIn(part, diagnostic)

    def test_real_cmd_both_branches(self):
        for branch in ['existing', 'new']:
            for code in [0, 1, 7]:
                with self.subTest(branch=branch, code=code):
                    with tempfile.TemporaryDirectory(prefix='startup-cmd-', dir=TEST_DIR) as temp:
                        log = Path(temp) / 'startup.log'
                        script = Path(temp) / 'startup-isolated.cmd'
                        script.write_text(guarded_cmd_fixture(CMD_SOURCE, code, branch, log), encoding='ascii')
                        run = subprocess.run(['cmd', '/d', '/c', str(script)], capture_output=True,
                                             text=True, errors='replace', timeout=5)
                        log_text = log.read_text(errors='replace')
                    print(f'CMD {branch} child={code} exit={run.returncode} '
                          f'stdout={run.stdout!r} stderr={run.stderr!r} log={log_text!r}')
                    self.assertEqual(run.returncode, code)
                    if code:
                        self.assertIn(f'exit={code}', run.stderr)
                        self.assertIn('startup.log', run.stderr)
                        self.assertIn(f'exit={code}', log_text)
                    else:
                        self.assertEqual(run.stderr, '')
                        self.assertEqual(log_text, '')

    def test_guards_and_parser(self):
        self.assertIn('wezterm-configure', guarded_cmd_fixture(CMD_SOURCE, 0, 'new', Path('D:/wezterm-configure/fake.log')))
        for bad in [PS_SOURCE.replace(EXPRESSION, 'blocked'), PS_SOURCE + '\n' + EXPRESSION]:
            with self.assertRaises(ValueError):
                guarded_ps_fixture(bad)
        with self.assertRaises(ValueError):
            guarded_cmd_fixture(CMD_SOURCE + '\nstart bad.exe', 7, 'new', Path('fake.log'))
        with self.assertRaises(ValueError):
            guarded_cmd_fixture(CMD_SOURCE + '\necho harmless & start bad.exe', 7, 'new', Path('fake.log'))
        path = str(SOURCE / 'Ensure-WorkbenchTabs.ps1').replace("'", "''")
        command = ("$tokens=$null;$errors=$null;[System.Management.Automation.Language.Parser]::"
                   f"ParseFile('{path}',[ref]$tokens,[ref]$errors)|Out-Null;"
                   "if($errors.Count){$errors|ForEach-Object{[Console]::Error.WriteLine($_)};exit 1};exit 0")
        run = subprocess.run(['powershell', '-NoProfile', '-Command', command], capture_output=True,
                             text=True, errors='replace', timeout=10)
        print(f'PARSER exit={run.returncode} stdout={run.stdout!r} stderr={run.stderr!r}')
        self.assertEqual(run.returncode, 0)


if __name__ == '__main__':
    for name in ['Ensure-WorkbenchTabs.ps1', 'Start-TerminalWorkbench.cmd']:
        print(f'SOURCE {SOURCE / name} SHA256={hashlib.sha256((SOURCE / name).read_bytes()).hexdigest()}')
    unittest.main(argv=[__file__, *unittest_args], verbosity=2)
