"""Isolated Control recovery contract; every platform effect is mocked."""
import copy
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / 'control_center.py'
if '--backend' in sys.argv:
    index = sys.argv.index('--backend')
    MODULE_PATH = Path(sys.argv[index + 1])
    del sys.argv[index:index + 2]
spec = importlib.util.spec_from_file_location('isolated_control_center', MODULE_PATH)
control = importlib.util.module_from_spec(spec)
with patch.dict(os.environ, {'TEST_CONTROL_SENTINEL': 'mock'}, clear=True):
    spec.loader.exec_module(control)


class ControlRestoreTests(unittest.TestCase):
    def setUp(self):
        self.reset_fixture()
        for target, attribute, replacement in [
                (control, '_workbench_tabs_lock', self.tabs_lock),
                (control.subprocess, 'run', self.run_cli),
                (Path, 'is_file', lambda path: str(path) not in self.missing_files)]:
            mock = patch.object(target, attribute, replacement, create=True)
            mock.start()
            self.addCleanup(mock.stop)
        mock = patch.object(control, 'reveal_terminal')
        self.reveal = mock.start()
        self.addCleanup(mock.stop)
        mock = patch.dict(os.environ, {'TEST_CONTROL_SENTINEL': 'mock'}, clear=True)
        mock.start()
        self.addCleanup(mock.stop)

    def reset_fixture(self):
        self.tabs = [{'tab_id': 6, 'position': 3, 'name': 'Control', 'active': False}]
        self.panes = [{'id': 13, 'is_plugin': False, 'title': 'Control',
                       'exited': True, 'is_held': True, 'exit_status': 1,
                       'is_floating': False, 'is_suppressed': False,
                       'terminal_command': str(control.GLAZE) + ' query workspaces',
                       'tab_id': 6, 'tab_position': 3, 'tab_name': 'Control',
                       'pane_x': 0, 'pane_y': 1, 'pane_rows': 30, 'pane_columns': 90}]
        self.actions, self.queries, self.timeouts, self.lock_events = [], [], [], []
        self.query_count = 0
        self.locked = False
        self.lock_failure = False
        self.fault_at = None
        self.fault = None
        self.drift = None
        self.missing_files = set()
        if hasattr(self, 'reveal'):
            self.reveal.reset_mock()

    @contextmanager
    def tabs_lock(self):
        self.lock_events.append('enter')
        if self.lock_failure:
            raise RuntimeError('mock lock failure')
        self.assertFalse(self.locked)
        self.locked = True
        try:
            yield
        finally:
            self.locked = False
            self.lock_events.append('exit')

    def run_cli(self, args, **kwargs):
        # The old Git implementation has no lock; permit it only for the red test.
        if hasattr(control, '_restore_control_locked'):
            self.assertTrue(self.locked)
        self.assertEqual(args[:4], [str(control.ZELLIJ), '--session', control.SESSION, 'action'])
        self.assertEqual(set(kwargs['env']),
                         {'TEST_CONTROL_SENTINEL', 'ZELLIJ_CONFIG_DIR', 'CNMPLAYER_ASSET_DIR'})
        self.assertEqual(kwargs['env']['TEST_CONTROL_SENTINEL'], 'mock')
        self.timeouts.append(kwargs['timeout'])
        action = args[4:]
        if action[0] in ('list-tabs', 'list-panes'):
            self.queries.append(action)
            self.query_count += 1
            if self.drift and self.query_count == 3:
                self.drift()
            if self.query_count == self.fault_at:
                if self.fault == 'timeout':
                    raise subprocess.TimeoutExpired(args, kwargs['timeout'])
                if self.fault == 'failure':
                    return subprocess.CompletedProcess(args, 1, '', 'mock query failure')
                return subprocess.CompletedProcess(args, 0, self.fault, '')
            if action == ['list-tabs', '--state']:
                return subprocess.CompletedProcess(args, 0, 'ID POSITION NAME\n6 3 Control\n', '')
            self.assertIn(action, [['list-tabs', '--json'], ['list-panes', '--all', '--json']])
            return subprocess.CompletedProcess(args, 0, json.dumps(
                self.tabs if action[0] == 'list-tabs' else self.panes), '')
        self.assertIn(action[0], ('new-pane', 'new-tab', 'go-to-tab'))
        self.actions.append(action)
        if self.fault_at == action[0]:
            if self.fault == 'timeout':
                raise subprocess.TimeoutExpired(args, kwargs['timeout'])
            return subprocess.CompletedProcess(args, 1, '', 'mock action failure')
        return subprocess.CompletedProcess(args, 0, '', '')

    def assert_refused(self):
        with self.assertRaises((RuntimeError, subprocess.TimeoutExpired)):
            control.restore_control()
        self.assertEqual(self.actions, [])
        self.reveal.assert_not_called()
        self.assertFalse(self.locked)
        if not self.lock_failure:
            self.assertEqual(self.lock_events, ['enter', 'exit'])

    def assert_replacement(self):
        result = control.restore_control()
        self.assertEqual(self.actions, [[
            'new-pane', '--in-place', '--close-replaced-pane', '--pane-id',
            'terminal_13', '--no-focus', '--name', 'Control', '--',
            str(control.ROOT / 'apps/spectrum-venv/Scripts/python.exe'),
            str(control.ROOT / 'apps/control-center/control_tui.py')]])
        self.assertEqual(self.queries, [['list-tabs', '--json'], ['list-panes', '--all', '--json']] * 2)
        self.assertEqual(self.timeouts, [5, 5, 5, 5, 10])
        self.assertEqual(self.lock_events, ['enter', 'exit'])
        self.assertIn('requested', result)
        self.reveal.assert_not_called()

    def test_original_exited_subquery_is_replaced_in_place_without_focus(self):
        self.assert_replacement()

    def test_fixed_python_and_glaze_display_forms_are_accepted(self):
        python = str(control.ROOT / 'apps/spectrum-venv/Scripts/python.exe')
        tui = str(control.ROOT / 'apps/control-center/control_tui.py')
        def forms(value):
            return [value, '"' + value + '"', value.replace('\\', '\\\\'),
                    '"' + value.replace('\\', '\\\\') + '"']
        commands = [p + ' ' + t for p in forms(python) for t in forms(tui)]
        commands += [g + ' query workspaces' for g in forms(str(control.GLAZE))]
        for command in commands:
            with self.subTest(command=command):
                self.reset_fixture()
                self.panes[0]['terminal_command'] = command
                self.assert_replacement()

    def test_alive_command_is_not_a_reason_to_replace(self):
        for command in (None, 'unknown.exe --child', self.panes[0]['terminal_command']):
            with self.subTest(command=command):
                self.reset_fixture()
                self.panes[0].update(exited=False, is_held=False, exit_status=None,
                                     terminal_command=command)
                self.assertIn('already exists', control.restore_control())
                self.assertEqual(self.actions, [['go-to-tab', '4']])
                self.assertEqual(len(self.queries), 4)
                self.reveal.assert_called_once_with()

    def test_missing_tab_uses_existing_layout_after_two_reads(self):
        self.tabs, self.panes = [], []
        self.assertIn('restored', control.restore_control())
        self.assertEqual(self.actions, [['new-tab', '--layout', str(control.CONTROL_LAYOUT), '--name', 'Control']])
        self.assertEqual(len(self.queries), 4)
        self.reveal.assert_called_once_with()

    def test_ambiguous_missing_and_wrong_ownership_are_refused(self):
        def duplicate_tab(): self.tabs.append(copy.deepcopy(self.tabs[0]))
        def alias_id(): self.tabs.append({'tab_id': 6, 'position': 8, 'name': 'Other'})
        def alias_position(): self.tabs.append({'tab_id': 8, 'position': 3, 'name': 'Other'})
        def duplicate_pane(): self.panes.append(copy.deepcopy(self.panes[0]))
        def extra_terminal():
            self.panes.append(dict(self.panes[0], id=14, title='Other'))
        def terminal_alias():
            self.panes.append(dict(self.panes[0], tab_id=8, tab_position=8, tab_name='Other'))
        cases = [duplicate_tab, alias_id, alias_position, duplicate_pane, extra_terminal,
                 terminal_alias, lambda: self.tabs.clear(), lambda: self.panes.clear()]
        cases += [lambda key=key, value=value: self.panes[0].update({key: value})
                  for key, value in [('title', 'Other'), ('tab_id', 8), ('tab_name', 'Other'),
                                     ('tab_position', 8), ('is_plugin', True),
                                     ('is_plugin', None), ('is_floating', True),
                                     ('is_suppressed', True), ('is_held', False),
                                     ('pane_rows', 0), ('pane_columns', 0)]]
        for index, change in enumerate(cases):
            with self.subTest(case=index):
                self.reset_fixture()
                change()
                self.assert_refused()

    def test_plugin_namespace_and_unrelated_commands_are_preserved(self):
        self.panes += [dict(self.panes[0], is_plugin=True, title='zellij:tab-bar'),
                       dict(self.panes[0], id=80, tab_id=9, tab_position=9,
                            tab_name='Other', terminal_command='private user task')]
        before = copy.deepcopy(self.panes)
        self.assert_replacement()
        self.assertEqual(self.panes, before)

    def test_strict_integer_boolean_exit_and_command_types(self):
        int_fields = [('tab', key) for key in ('tab_id', 'position')]
        int_fields += [('pane', key) for key in ('id', 'tab_id', 'tab_position', 'pane_x',
                                                'pane_y', 'pane_rows', 'pane_columns')]
        bool_fields = [('tab', 'active')] + [('pane', key) for key in
                       ('is_plugin', 'exited', 'is_held', 'is_floating', 'is_suppressed')]
        cases = [(subject, key, value) for subject, key in int_fields
                 for value in (True, '6', -1, None)]
        cases += [(subject, key, value) for subject, key in bool_fields for value in (None, 0, 'false')]
        cases += [('pane', 'exit_status', value) for value in (None, True, '1', -1)]
        cases += [('pane', 'terminal_command', value) for value in (None, 1, ['bad'])]
        for subject, key, value in cases:
            with self.subTest(subject=subject, key=key, value=value):
                self.reset_fixture()
                (self.tabs if subject == 'tab' else self.panes)[0][key] = value
                self.assert_refused()

    def test_unknown_command_forms_are_refused_without_normalizing(self):
        python = str(control.ROOT / 'apps/spectrum-venv/Scripts/python.exe')
        tui = str(control.ROOT / 'apps/control-center/control_tui.py')
        command = python + ' ' + tui
        glaze = str(control.GLAZE) + ' query workspaces'
        commands = [command + ' --other', '"' + command + '"', "'" + python + "' " + tui,
                    '""' + python + '"" ' + tui, '"' + command, command + '"',
                    command.upper(), command.replace('\\', '/'), command.replace(' ', '\t'),
                    ' ' + command, command + ' ', command + '\n', command.replace(' ', '  '),
                    command + ' & other', command + ';other', command + '|other',
                    command.replace('control-center', 'elsewhere\\..\\control-center'),
                    python + ' -u ' + tui, glaze.replace('workspaces', 'windows'),
                    glaze.replace('query', 'QUERY'), str(control.GLAZE) + ' "query" workspaces',
                    r'C:\Python\python.exe' + ' ' + tui, 'python.exe ' + tui]
        for candidate in commands:
            with self.subTest(command=candidate):
                self.reset_fixture()
                self.panes[0]['terminal_command'] = candidate
                self.assert_refused()

    def test_missing_executable_or_tui_is_refused(self):
        for path in (control.CONTROL_PYTHON, control.CONTROL_TUI):
            with self.subTest(path=str(path)):
                self.reset_fixture()
                self.missing_files.add(str(path))
                self.assert_refused()

    def test_each_query_failure_timeout_and_bad_payload_is_refused(self):
        for count in range(1, 5):
            for fault in ('failure', 'timeout', 'broken JSON', '{}', '["bad record"]'):
                with self.subTest(query=count, fault=fault):
                    self.reset_fixture()
                    self.fault_at, self.fault = count, fault
                    self.assert_refused()

    def test_every_identity_state_command_and_geometry_drift_is_refused(self):
        changes = [('tab', 'tab_id', 7), ('tab', 'position', 4), ('tab', 'name', 'Other'),
                   ('tab', 'active', True), ('pane', 'id', 14), ('pane', 'tab_id', 7),
                   ('pane', 'tab_position', 4), ('pane', 'tab_name', 'Other'),
                   ('pane', 'title', 'Other'), ('pane', 'is_plugin', True),
                   ('pane', 'exited', False), ('pane', 'is_held', False),
                   ('pane', 'is_floating', True), ('pane', 'is_suppressed', True),
                   ('pane', 'exit_status', 2), ('pane', 'terminal_command', '"' + str(control.GLAZE) + '" query workspaces'),
                   ('pane', 'pane_x', 1), ('pane', 'pane_y', 2),
                   ('pane', 'pane_rows', 31), ('pane', 'pane_columns', 91)]
        for subject, key, value in changes:
            with self.subTest(subject=subject, key=key):
                self.reset_fixture()
                self.drift = lambda: (self.tabs if subject == 'tab' else self.panes)[0].update({key: value})
                self.assert_refused()

    def test_missing_to_present_and_present_to_missing_drift_is_refused(self):
        for initially_missing in (False, True):
            with self.subTest(initially_missing=initially_missing):
                self.reset_fixture()
                saved = copy.deepcopy((self.tabs, self.panes))
                if initially_missing:
                    self.tabs, self.panes = [], []
                self.drift = lambda: self.__dict__.update(
                    tabs=saved[0] if initially_missing else [], panes=saved[1] if initially_missing else [])
                self.assert_refused()

    def test_lock_failure_occurs_before_any_query(self):
        self.lock_failure = True
        self.assert_refused()
        self.assertEqual(self.queries, [])

    def test_mutation_failure_and_timeout_never_retry_or_reveal(self):
        for action in ('new-pane', 'new-tab', 'go-to-tab'):
            for fault in ('failure', 'timeout'):
                with self.subTest(action=action, fault=fault):
                    self.reset_fixture()
                    if action == 'new-tab':
                        self.tabs, self.panes = [], []
                    elif action == 'go-to-tab':
                        self.panes[0].update(exited=False, is_held=False, exit_status=None)
                    self.fault_at, self.fault = action, fault
                    with self.assertRaises((RuntimeError, subprocess.TimeoutExpired)):
                        control.restore_control()
                    self.assertEqual(len(self.actions), 1)
                    self.assertEqual(self.actions[0][0], action)
                    self.reveal.assert_not_called()
                    self.assertEqual(self.lock_events, ['enter', 'exit'])

    def test_repeated_restore_keeps_new_alive_pane(self):
        control.restore_control()
        self.panes[0].update(id=20, exited=False, is_held=False, exit_status=None)
        control.restore_control()
        self.assertEqual([action[0] for action in self.actions], ['new-pane', 'go-to-tab'])
        self.assertEqual(self.lock_events, ['enter', 'exit', 'enter', 'exit'])


if __name__ == '__main__':
    unittest.main()
