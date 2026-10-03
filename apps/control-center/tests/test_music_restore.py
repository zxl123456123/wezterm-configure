import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / 'control_center.py'
spec = importlib.util.spec_from_file_location('staged_control_center', MODULE_PATH)
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


class MusicRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lock_patch = patch.object(control, 'MUSIC_RESTORE_LOCK', Path(self.temp.name) / 'restore.lock', create=True)
        self.lock_patch.start()
        self.addCleanup(self.lock_patch.stop)
        self.tabs = [{'tab_id': 6, 'position': 3, 'name': 'Music', 'active': False}]
        self.panes = [{'id': 13, 'is_plugin': False, 'title': 'Player',
                       'exited': True, 'is_held': True, 'terminal_command':
                       r'D:\terminal-workbench\apps\cnmplayer\cnmplayer.exe',
                       'tab_id': 6, 'tab_position': 3, 'tab_name': 'Music'}]
        self.actions = []
        self.queries = []
        self.failure = None
        self.invalid_json = None
        self.drift = None
        self.query_count = 0
        self.run_patch = patch.object(control.subprocess, 'run', side_effect=self.run_cli)
        self.run_patch.start()
        self.addCleanup(self.run_patch.stop)
        self.reveal_patch = patch.object(control, 'reveal_terminal')
        self.reveal = self.reveal_patch.start()
        self.addCleanup(self.reveal_patch.stop)
        self.env_patch = patch.dict(os.environ, {'TEST_RESTORE_SENTINEL': 'mock'}, clear=True)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def run_cli(self, args, **kwargs):
        action = args[args.index('action') + 1:]
        self.assertEqual(kwargs['env']['TEST_RESTORE_SENTINEL'], 'mock')
        self.assertIn('CNMPLAYER_ASSET_DIR', kwargs['env'])
        if action[0] in ('list-tabs', 'list-panes'):
            self.queries.append(action)
            self.query_count += 1
            if self.drift and self.query_count == 3:
                self.drift()
            if self.failure == action[0]:
                return subprocess.CompletedProcess(args, 1, '', 'mock query failure')
            if self.invalid_json == action[0]:
                return subprocess.CompletedProcess(args, 0, 'broken JSON', '')
            if action == ['list-tabs', '--state']:
                return subprocess.CompletedProcess(args, 0, 'ID POSITION NAME\n6 3 Music\n', '')
            payload = self.tabs if action[0] == 'list-tabs' else self.panes
            return subprocess.CompletedProcess(args, 0, json.dumps(payload), '')
        self.actions.append(action)
        if self.failure == action[0]:
            return subprocess.CompletedProcess(args, 1, '', 'mock action failure')
        return subprocess.CompletedProcess(args, 0, '', '')

    def assert_refused(self):
        with self.assertRaises((RuntimeError, ValueError)):
            control.restore_music()
        self.assertEqual(self.actions, [])
        self.reveal.assert_not_called()

    def test_exited_player_is_replaced_then_shown_without_input(self):
        result = control.restore_music()
        self.assertEqual(self.actions, [[
            'new-pane', '--in-place', '--close-replaced-pane', '--pane-id',
            'terminal_13', '--no-focus', '--name', 'Player', '--',
            str(control.ROOT / 'apps' / 'cnmplayer' / 'cnmplayer.exe')],
            ['go-to-tab-by-id', '6']])
        self.assertIn('restored', result)
        self.assertEqual(self.queries, [['list-tabs', '--json'], ['list-panes', '--all', '--json']] * 2)
        self.reveal.assert_called_once_with()

    def test_active_player_keeps_existing_jump_behavior(self):
        self.panes[0].update(exited=False, is_held=False)
        self.assertIn('already exists', control.restore_music())
        self.assertEqual(self.actions, [['go-to-tab', '4']])
        self.reveal.assert_called_once_with()

    def test_missing_tab_uses_existing_layout(self):
        self.tabs = []
        self.panes = []
        control.restore_music()
        self.assertEqual(self.actions, [['new-tab', '--layout', str(control.MUSIC_LAYOUT), '--name', 'Music']])
        self.reveal.assert_called_once_with()

    def test_missing_player_is_not_silently_created(self):
        self.panes = []
        self.assert_refused()

    def test_duplicate_tabs_and_players_are_refused(self):
        for subject in ('tabs', 'panes'):
            with self.subTest(subject=subject):
                collection = getattr(self, subject)
                collection.append(copy.deepcopy(collection[0]))
                self.assert_refused()
                collection.pop()

    def test_plugin_player_is_not_a_terminal_target(self):
        self.panes[0]['is_plugin'] = True
        self.assert_refused()

    def test_wrong_command_unheld_and_invalid_ids_are_refused(self):
        for key, value in [('terminal_command', 'cnmplayer.exe'),
                           ('terminal_command', str(control.ROOT / 'apps/cnmplayer/cnmplayer.exe') + ' --other'),
                           ('terminal_command', r'D:\elsewhere\cnmplayer.exe'),
                           ('is_held', False), ('exited', None), ('id', '13'),
                           ('tab_position', 4), ('tab_name', 'Other')]:
            with self.subTest(key=key, value=value):
                original = self.panes[0][key]
                self.panes[0][key] = value
                self.assert_refused()
                self.panes[0][key] = original

    def test_normalized_quoted_full_path_is_accepted(self):
        self.panes[0]['terminal_command'] = '"D:/TERMINAL-WORKBENCH/apps/cnmplayer/../cnmplayer/cnmplayer.exe"'
        control.restore_music()
        self.assertEqual(self.actions[0][0], 'new-pane')

    def test_query_errors_and_invalid_json_fail_closed(self):
        for action in ('list-tabs', 'list-panes'):
            for field in ('failure', 'invalid_json'):
                with self.subTest(action=action, field=field):
                    setattr(self, field, action)
                    self.assert_refused()
                    setattr(self, field, None)

    def test_state_and_identity_drift_abort_before_write(self):
        original_tabs, original_panes = copy.deepcopy(self.tabs), copy.deepcopy(self.panes)
        for subject, key, value in [('pane', 'id', 14), ('pane', 'exited', False),
                                    ('pane', 'terminal_command', 'other.exe'),
                                    ('pane', 'is_held', False), ('tab', 'tab_id', 7),
                                    ('tab', 'position', 4)]:
            with self.subTest(subject=subject, key=key):
                self.tabs, self.panes = copy.deepcopy(original_tabs), copy.deepcopy(original_panes)
                self.query_count = 0
                self.drift = lambda: (self.panes[0] if subject == 'pane' else self.tabs[0]).update({key: value})
                self.assert_refused()

    def test_new_tab_appearing_during_query_aborts_creation(self):
        self.tabs = []
        self.panes = []
        self.drift = lambda: self.tabs.append({'tab_id': 6, 'position': 3, 'name': 'Music'})
        self.assert_refused()

    def test_action_failure_is_reported(self):
        for action in ('new-pane', 'go-to-tab', 'new-tab', 'go-to-tab-by-id'):
            with self.subTest(action=action):
                self.tabs = [] if action == 'new-tab' else [{'tab_id': 6, 'position': 3, 'name': 'Music'}]
                self.panes[0].update(exited=action != 'go-to-tab', is_held=action != 'go-to-tab')
                self.actions.clear()
                self.failure = action
                with self.assertRaisesRegex(RuntimeError, 'mock action failure'):
                    control.restore_music()
                self.assertEqual(len(self.actions), 2 if action == 'go-to-tab-by-id' else 1)
                self.reveal.assert_not_called()

    def test_malformed_tab_identity_and_json_records_fail_closed(self):
        for value in ('6', True, -1, None):
            with self.subTest(value=value):
                self.tabs[0]['tab_id'] = value
                self.assert_refused()
        for records in ({'tabs': []}, ['bad record']):
            with self.subTest(records=records):
                self.tabs = records
                self.assert_refused()

    def test_query_failure_during_recheck_aborts_write(self):
        self.drift = lambda: setattr(self, 'failure', 'list-panes')
        self.assert_refused()

    def test_duplicate_restore_is_locked_before_query(self):
        import msvcrt
        with open(control.MUSIC_RESTORE_LOCK, 'w+b') as lock:
            lock.write(b'0')
            lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                with self.assertRaisesRegex(RuntimeError, 'already in progress'):
                    control.restore_music()
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        self.assertEqual(self.queries, [])
        self.assertEqual(self.actions, [])

    def test_lock_is_released_after_failure(self):
        self.failure = 'list-tabs'
        self.assert_refused()
        self.failure = None
        control.restore_music()
        self.assertEqual([action[0] for action in self.actions], ['new-pane', 'go-to-tab-by-id'])

    def test_repeated_restore_does_not_create_second_player(self):
        control.restore_music()
        self.panes[0].update(id=20, exited=False, is_held=False)
        control.restore_music()
        self.assertEqual([action[0] for action in self.actions], ['new-pane', 'go-to-tab-by-id', 'go-to-tab'])


if __name__ == '__main__':
    unittest.main()
