"""Local workbench controller: WezTerm appearance and GlazeWM windows."""

import ctypes
from ctypes import wintypes
from contextlib import contextmanager
import json
import mimetypes
import msvcrt
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


ROOT = Path(r'D:\terminal-workbench')
HERE = Path(__file__).resolve().parent
APPEARANCE = ROOT / 'config' / 'wezterm' / 'appearance.json'
WEZTERM_CONFIG = ROOT / 'config' / 'wezterm' / 'wezterm.lua'
IMAGES = ROOT / 'images'
GLAZE = ROOT / 'apps' / 'glazewm' / 'cli' / 'glazewm.exe'
ZELLIJ = ROOT / 'apps' / 'zellij' / 'zellij.exe'
MUSIC_LAYOUT = ROOT / 'config' / 'zellij' / 'layouts' / 'music.kdl'
MUSIC_PLAYER = ROOT / 'apps' / 'cnmplayer' / 'cnmplayer.exe'
MUSIC_RESTORE_LOCK = ROOT / 'data' / 'music-restore.lock'
CONTROL_LAYOUT = ROOT / 'config' / 'zellij' / 'layouts' / 'control.kdl'
CONTROL_PYTHON = ROOT / 'apps' / 'spectrum-venv' / 'Scripts' / 'python.exe'
CONTROL_TUI = ROOT / 'apps' / 'control-center' / 'control_tui.py'
SESSION = 'workbench-v4'
PORT = 8765
URL = f'http://127.0.0.1:{PORT}/'
TOKEN = secrets.token_urlsafe(24)


def image_names():
    allowed = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'}
    if not IMAGES.is_dir():
        return []
    return sorted(p.name for p in IMAGES.iterdir() if p.is_file() and p.suffix.lower() in allowed)


def get_appearance():
    defaults = {'image': 'terminal-background.png'}
    try:
        defaults.update(json.loads(APPEARANCE.read_text(encoding='utf-8')))
    except (OSError, ValueError):
        pass
    return defaults


def save_appearance(data):
    current = get_appearance()
    if 'image' in data:
        if data['image'] not in ['none', *image_names()]:
            raise ValueError('Choose a file in D:\\terminal-workbench\\images')
        if data['image'] != 'none':
            from PIL import Image, UnidentifiedImageError
            path = IMAGES / data['image']
            if path.stat().st_size > 30 * 1024 * 1024:
                raise ValueError('Background image must be smaller than 30 MB')
            try:
                with Image.open(path) as picture:
                    if picture.width * picture.height > 80_000_000:
                        raise ValueError('Background image is too large')
                    picture.verify()
            except (OSError, UnidentifiedImageError) as exc:
                raise ValueError('Background image cannot be opened') from exc
        current['image'] = data['image']
    temp_path = APPEARANCE.with_name('.appearance-' + secrets.token_hex(6) + '.tmp')
    try:
        temp_path.write_text(json.dumps({'image': current['image']}, ensure_ascii=False,
                                        indent=2) + '\n', encoding='utf-8')
        os.replace(temp_path, APPEARANCE)
    finally:
        temp_path.unlink(missing_ok=True)
    # WezTerm watches appearance.json; touching the Lua config also covers older builds.
    WEZTERM_CONFIG.touch()
    return current


def glaze_query(subject):
    result = subprocess.run([str(GLAZE), 'query', subject], capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=5)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'GlazeWM is not running')
    payload = json.loads(result.stdout)
    if not payload.get('success'):
        raise RuntimeError(str(payload.get('error') or 'GlazeWM query failed'))
    return payload['data']


def workspace_state():
    workspaces = glaze_query('workspaces')['workspaces']
    try:
        monitors = glaze_query('monitors')['monitors']
    except Exception:
        monitors = []
    monitor_by_workspace = {}
    def collect_monitor_workspaces(node, label):
        if node.get('type') == 'workspace':
            monitor_by_workspace[node.get('id')] = label
        for child in node.get('children', []):
            collect_monitor_workspaces(child, label)
    for index, monitor in enumerate(monitors, 1):
        label = monitor.get('name') or monitor.get('displayName') or f'显示器 {index}'
        collect_monitor_workspaces(monitor, label)
        for ws_id in monitor.get('workspaceIds', []):
            monitor_by_workspace[ws_id] = label
        for ws in workspaces:
            if ws.get('parentId') == monitor.get('id'):
                monitor_by_workspace[ws['id']] = label
    groups = []
    for ws in workspaces:
        items = []
        def visit(node):
            if node.get('type') == 'window':
                items.append({key: node.get(key) for key in
                              ('id', 'title', 'processName', 'hasFocus', 'displayState')})
                items[-1]['state'] = (node.get('state') or {}).get('type', 'unknown')
            for child in node.get('children', []):
                visit(child)
        visit(ws)
        groups.append({'id': ws['id'], 'name': ws['name'],
                       'displayName': ws.get('displayName') or ws['name'],
                       'monitor': monitor_by_workspace.get(ws['id'], '未分配显示器'),
                       'hasFocus': ws.get('hasFocus', False),
                       'isDisplayed': ws.get('isDisplayed', False), 'windows': items})
    return groups


def run_glaze(action, window_id, workspace=None):
    groups = workspace_state()
    valid_ids = {win['id'] for group in groups for win in group['windows']}
    valid_ws = {group['name'] for group in groups}
    if window_id not in valid_ids:
        raise ValueError('Window is no longer managed by GlazeWM; refresh the page')
    if action == 'focus':
        args = ['command', 'focus', '--container-id', window_id]
    elif action == 'move' and workspace in valid_ws:
        args = ['command', '--id', window_id, 'move', '--workspace', workspace]
    else:
        raise ValueError('Invalid action or workspace')
    result = subprocess.run([str(GLAZE), *args], capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=6)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'Command failed')
    payload = json.loads(result.stdout)
    if not payload.get('success'):
        raise RuntimeError(str(payload.get('error') or 'GlazeWM command failed'))
    return payload.get('data') or 'Done'


@contextmanager
def _workbench_tabs_lock():
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.ReleaseMutex.argtypes = [wintypes.HANDLE]
    kernel32.ReleaseMutex.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.CreateMutexW(None, False, r'Local\TerminalWorkbench.Tabs.workbench-v4')
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    owned = False
    try:
        status = kernel32.WaitForSingleObject(handle, 30000)
        if status in (0, 0x80):
            # Both normal and abandoned acquisition give this thread ownership.
            owned = True
        elif status == 0x102:
            raise RuntimeError('Workbench tab lock wait timed out after 30000ms; try again shortly.')
        elif status == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        else:
            raise RuntimeError(f'Unexpected workbench tab lock wait result: {status}')
        yield
    finally:
        primary_error = sys.exc_info()[1]
        cleanup_error = None
        if owned:
            try:
                if not kernel32.ReleaseMutex(handle):
                    raise ctypes.WinError(ctypes.get_last_error())
            except BaseException as exc:
                cleanup_error = exc
        # Closing the handle is independent of releasing this thread's ownership.
        try:
            if not kernel32.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException as exc:
            if cleanup_error is None:
                cleanup_error = exc
        if cleanup_error is not None:
            if primary_error is None:
                raise cleanup_error
            try:
                print(f'Workbench tab lock cleanup failed: {cleanup_error}', file=sys.stderr)
            except Exception:
                pass



def restore_tab(name, layout):
    env = os.environ.copy()
    env['ZELLIJ_CONFIG_DIR'] = str(ROOT / 'config' / 'zellij')
    env['CNMPLAYER_ASSET_DIR'] = str(ROOT / 'data' / 'cnmplayer')
    listing = subprocess.run([str(ZELLIJ), '--session', SESSION, 'action',
                              'list-tabs', '--state'], capture_output=True,
                             text=True, encoding='utf-8', errors='replace', env=env, timeout=5)
    if listing.returncode:
        raise RuntimeError('Workbench session is not running. Open Start-DesktopWorkbench.cmd first.')
    for line in listing.stdout.splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 3 and fields[2] == name:
            subprocess.run([str(ZELLIJ), '--session', SESSION, 'action',
                            'go-to-tab', str(int(fields[1]) + 1)], env=env,
                           check=True, timeout=5)
            reveal_terminal()
            return f'{name} tab already exists; switched to it.'
    result = subprocess.run([str(ZELLIJ), '--session', SESSION, 'action', 'new-tab',
                             '--layout', str(layout), '--name', name],
                            capture_output=True, text=True, encoding='utf-8',
                            errors='replace', env=env, timeout=10)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f'Could not restore {name} tab')
    reveal_terminal()
    return f'{name} tab restored.'


def reveal_terminal():
    """Unminimize the workbench when a launcher is used outside WezTerm."""
    try:
        windows = glaze_query('windows')['windows']
        target = next((win for win in windows if win.get('processName') == 'wezterm-gui'
                       and win.get('title') == 'Terminal Workbench'), None)
        if target is None:
            return
        if (target.get('state') or {}).get('type') == 'minimized':
            result = subprocess.run([str(GLAZE), 'command', '--id', target['id'],
                                     'toggle-minimized'], capture_output=True, text=True,
                                    encoding='utf-8', errors='replace', timeout=5)
            if result.returncode or not json.loads(result.stdout).get('success'):
                return
        subprocess.run([str(GLAZE), 'command', 'focus', '--container-id', target['id']],
                       capture_output=True, timeout=5)
    except Exception:
        pass


def restore_music():
    # The launcher and dashboard must not replace the same exited pane twice.
    with open(MUSIC_RESTORE_LOCK, 'a+b') as lock:
        lock.seek(0, os.SEEK_END)
        if lock.tell() == 0:
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError('Music restore is already in progress; try again shortly.') from exc
        try:
            return _restore_music_locked()
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def _restore_music_locked():
    env = os.environ.copy()
    env['ZELLIJ_CONFIG_DIR'] = str(ROOT / 'config' / 'zellij')
    env['CNMPLAYER_ASSET_DIR'] = str(ROOT / 'data' / 'cnmplayer')

    def run_action(args, timeout=5):
        result = subprocess.run([str(ZELLIJ), '--session', SESSION, 'action', *args],
                                capture_output=True, text=True, encoding='utf-8',
                                errors='replace', env=env, timeout=timeout)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip()
                               or f'Music restore command failed: {args[0]}')
        return result.stdout

    def query(args):
        try:
            records = json.loads(run_action(args))
        except ValueError as exc:
            raise RuntimeError(f'Invalid JSON from {args[0]}') from exc
        if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
            raise RuntimeError(f'Invalid state from {args[0]}')
        return records

    def player_state():
        tabs = query(['list-tabs', '--json'])
        panes = query(['list-panes', '--all', '--json'])
        matches = [tab for tab in tabs if tab.get('name') == 'Music']
        if not matches:
            return None
        if len(matches) != 1:
            raise RuntimeError('Music tab is ambiguous; no pane was changed.')
        tab = matches[0]
        if any(type(tab.get(key)) is not int or tab[key] < 0 for key in ('tab_id', 'position')):
            raise RuntimeError('Music tab identity is invalid; no pane was changed.')
        players = [pane for pane in panes if pane.get('tab_id') == tab['tab_id']
                   and pane.get('title') == 'Player' and pane.get('is_plugin') is False]
        if len(players) != 1:
            raise RuntimeError('Music needs exactly one terminal Player pane; no pane was changed.')
        pane = players[0]
        command = pane.get('terminal_command')
        if not isinstance(command, str):
            raise RuntimeError('Player command is unknown; no pane was changed.')
        if command.startswith('"') and command.endswith('"'):
            command = command[1:-1]
        command = os.path.normcase(os.path.normpath(command))
        expected = os.path.normcase(os.path.normpath(str(MUSIC_PLAYER)))
        if command != expected:
            raise RuntimeError('Player command does not match CNMPlayer; no pane was changed.')
        if (type(pane.get('id')) is not int or pane['id'] < 0
                or pane.get('tab_name') != 'Music' or pane.get('tab_position') != tab['position']
                or type(pane.get('exited')) is not bool or type(pane.get('is_held')) is not bool):
            raise RuntimeError('Player identity or state is invalid; no pane was changed.')
        if pane['exited'] and not pane['is_held']:
            raise RuntimeError('Exited Player is not held; no pane was changed.')
        return (tab['tab_id'], tab['position'], pane['id'], pane['exited'], pane['is_held'], command)

    state = player_state()
    if player_state() != state:
        raise RuntimeError('Music state changed during restore; retry without changing other panes.')
    if state is None:
        run_action(['new-tab', '--layout', str(MUSIC_LAYOUT), '--name', 'Music'], timeout=10)
        reveal_terminal()
        return 'Music tab restored.'
    tab_id, position, pane_id, exited, _, _ = state
    if not exited:
        run_action(['go-to-tab', str(position + 1)])
        reveal_terminal()
        return 'Music tab already exists; switched to it.'
    run_action(['new-pane', '--in-place', '--close-replaced-pane', '--pane-id',
                f'terminal_{pane_id}', '--no-focus', '--name', 'Player', '--',
                str(MUSIC_PLAYER)], timeout=10)
    run_action(['go-to-tab-by-id', str(tab_id)])
    reveal_terminal()
    return 'Music Player restored in its existing pane.'


def _restore_control_locked():
    env = os.environ.copy()
    env['ZELLIJ_CONFIG_DIR'] = str(ROOT / 'config' / 'zellij')
    env['CNMPLAYER_ASSET_DIR'] = str(ROOT / 'data' / 'cnmplayer')

    def run_action(args, timeout=5):
        result = subprocess.run([str(ZELLIJ), '--session', SESSION, 'action', *args],
                                capture_output=True, text=True, encoding='utf-8',
                                errors='replace', env=env, timeout=timeout)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip()
                               or f'Control restore command failed: {args[0]}')
        return result.stdout

    def query(args):
        try:
            records = json.loads(run_action(args))
        except ValueError as exc:
            raise RuntimeError(f'Invalid JSON from {args[0]}') from exc
        if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
            raise RuntimeError(f'Invalid state from {args[0]}')
        return records

    def control_state():
        tabs = query(['list-tabs', '--json'])
        panes = query(['list-panes', '--all', '--json'])
        matches = [tab for tab in tabs if tab.get('name') == 'Control']
        if not matches:
            if any(pane.get('tab_name') == 'Control' for pane in panes):
                raise RuntimeError('Control panes have no tab; no pane was changed.')
            return None
        if len(matches) != 1:
            raise RuntimeError('Control tab is ambiguous; no pane was changed.')
        tab = matches[0]
        if (any(type(tab.get(key)) is not int or tab[key] < 0
                for key in ('tab_id', 'position')) or type(tab.get('active')) is not bool):
            raise RuntimeError('Control tab identity is invalid; no pane was changed.')
        if any(other is not tab and (other.get('tab_id') == tab['tab_id']
                                    or other.get('position') == tab['position']) for other in tabs):
            raise RuntimeError('Control tab identity is aliased; no pane was changed.')
        related = [pane for pane in panes if pane.get('tab_id') == tab['tab_id']
                   or pane.get('tab_name') == 'Control']
        for pane in related:
            if (type(pane.get('tab_id')) is not int or pane['tab_id'] != tab['tab_id']
                    or type(pane.get('tab_position')) is not int
                    or pane['tab_position'] != tab['position'] or pane.get('tab_name') != 'Control'
                    or type(pane.get('is_plugin')) is not bool
                    or (pane['is_plugin'] and pane.get('title') == 'Control')):
                raise RuntimeError('Control pane ownership is invalid; no pane was changed.')
        terminals = [pane for pane in related if pane['is_plugin'] is False]
        if len(terminals) != 1 or terminals[0].get('title') != 'Control':
            raise RuntimeError('Control needs exactly one terminal Control pane; no pane was changed.')
        pane = terminals[0]
        if (any(type(pane.get(key)) is not int or pane[key] < 0
                for key in ('id', 'tab_id', 'tab_position', 'pane_x', 'pane_y',
                            'pane_rows', 'pane_columns'))
                or pane['pane_rows'] == 0 or pane['pane_columns'] == 0
                or any(type(pane.get(key)) is not bool for key in
                       ('exited', 'is_held', 'is_floating', 'is_suppressed'))
                or pane['is_floating'] or pane['is_suppressed']):
            raise RuntimeError('Control pane identity or state is invalid; no pane was changed.')
        if sum(other.get('is_plugin') is False and other.get('id') == pane['id']
               for other in panes) != 1:
            raise RuntimeError('Control terminal identity is duplicated; no pane was changed.')
        status = pane.get('exit_status')
        command = pane.get('terminal_command')
        if ((status is not None and type(status) is not int)
                or (command is not None and not isinstance(command, str))
                or (pane['exited'] and (not pane['is_held'] or type(status) is not int or status < 0))):
            raise RuntimeError('Control exit state or command is invalid; no pane was changed.')
        return (tab['tab_id'], tab['position'], tab['name'], tab['active'],
                pane['id'], pane['tab_id'], pane['tab_position'], pane['tab_name'],
                pane['title'], pane['is_plugin'], pane['exited'], pane['is_held'],
                pane['is_floating'], pane['is_suppressed'], status, command,
                pane['pane_x'], pane['pane_y'], pane['pane_rows'], pane['pane_columns'])

    state = control_state()
    if control_state() != state:
        raise RuntimeError('Control state changed during restore; no pane was changed.')
    if state is None:
        run_action(['new-tab', '--layout', str(CONTROL_LAYOUT), '--name', 'Control'], timeout=10)
        reveal_terminal()
        return 'Control tab restored.'
    position, pane_id, exited, command = state[1], state[4], state[10], state[15]
    if not exited:
        run_action(['go-to-tab', str(position + 1)])
        reveal_terminal()
        return 'Control tab already exists; switched to it.'

    # Fixed display forms only; no shell parsing or command normalization.
    def path_forms(path):
        plain = str(path)
        displayed = plain.replace('\\', '\\\\')
        return (plain, '"' + plain + '"', displayed, '"' + displayed + '"')

    allowed = {python + ' ' + tui for python in path_forms(CONTROL_PYTHON)
               for tui in path_forms(CONTROL_TUI)}
    allowed.update(glaze + ' query workspaces' for glaze in path_forms(GLAZE))
    if command not in allowed:
        raise RuntimeError('Control command is unknown; no pane was changed.')
    if not CONTROL_PYTHON.is_file() or not CONTROL_TUI.is_file():
        raise RuntimeError('Control executable or TUI is missing; no pane was changed.')
    run_action(['new-pane', '--in-place', '--close-replaced-pane', '--pane-id',
                f'terminal_{pane_id}', '--no-focus', '--name', 'Control', '--',
                str(CONTROL_PYTHON), str(CONTROL_TUI)], timeout=10)
    return 'Control restore requested in its existing pane.'


def restore_control():
    with _workbench_tabs_lock():
        return _restore_control_locked()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def reply(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.headers.get('Host') not in (f'127.0.0.1:{PORT}', f'localhost:{PORT}'):
            return self.reply(403, {'error': 'Local access only'})
        if self.path == '/health':
            return self.reply(200, {'app': 'terminal-workbench-control'})
        if self.path == '/':
            page = (HERE / 'dashboard.html').read_text(encoding='utf-8').replace('__TOKEN__', TOKEN)
            body = page.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            return self.wfile.write(body)
        if self.path.startswith('/images/'):
            name = self.path.removeprefix('/images/')
            if name not in image_names():
                return self.reply(404, {'error': 'Image not found'})
            image = IMAGES / name
            body = image.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', mimetypes.guess_type(name)[0] or 'application/octet-stream')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            return self.wfile.write(body)
        if self.path == '/api/state':
            try:
                return self.reply(200, {'workspaces': workspace_state(),
                                        'appearance': get_appearance(), 'images': image_names()})
            except Exception as exc:
                return self.reply(200, {'workspaces': [], 'appearance': get_appearance(),
                                        'images': image_names(), 'warning': str(exc)})
        return self.reply(404, {'error': 'Not found'})

    def do_POST(self):
        if self.headers.get('Host') not in (f'127.0.0.1:{PORT}', f'localhost:{PORT}'):
            return self.reply(403, {'error': 'Local access only'})
        if self.headers.get('X-Workbench-Token') != TOKEN:
            return self.reply(403, {'error': 'Invalid control token'})
        if int(self.headers.get('Content-Length', '0')) > 4096:
            return self.reply(413, {'error': 'Request too large'})
        try:
            data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
            if self.path == '/api/appearance':
                result = save_appearance(data)
            elif self.path == '/api/window':
                result = run_glaze(data.get('action'), data.get('id'), data.get('workspace'))
            elif self.path == '/api/music':
                result = restore_music()
            else:
                return self.reply(404, {'error': 'Not found'})
            return self.reply(200, {'ok': True, 'result': result})
        except Exception as exc:
            return self.reply(400, {'error': str(exc)})


def health():
    try:
        with urllib.request.urlopen(URL + 'health', timeout=0.5) as response:
            return json.load(response).get('app') == 'terminal-workbench-control'
    except Exception:
        return False


def open_dashboard():
    if not health():
        pythonw = Path(sys.executable).with_name('pythonw.exe')
        subprocess.Popen([str(pythonw), str(Path(__file__).resolve()), 'server'],
                         cwd=str(HERE), creationflags=subprocess.CREATE_NO_WINDOW,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        for _ in range(40):
            if health():
                break
            time.sleep(0.1)
    if not health():
        raise RuntimeError('Control center server did not start')
    webbrowser.open(URL)
    return URL


def tui():
    while True:
        cfg = get_appearance()
        print('\n=== Workbench Control ===')
        print(f"1  Background image: {cfg['image']}")
        print('2  Open window control dashboard in browser')
        print('3  Restore or jump to Music tab')
        print('q  Quit this control pane (tab remains open)')
        choice = input('Choose: ').strip().lower()
        try:
            if choice == '1':
                names = ['none', *image_names()]
                for i, name in enumerate(names):
                    print(f'{i}: {name}')
                index = int(input('Image number: '))
                save_appearance({'image': names[index]})
            elif choice == '2':
                print('Opened:', open_dashboard())
            elif choice == '3':
                print(restore_music())
            elif choice == 'q':
                return
        except (ValueError, IndexError, RuntimeError, OSError) as exc:
            print('Error:', exc)


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'tui'
    if mode == 'server':
        ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
    elif mode == 'open':
        print(open_dashboard())
    elif mode == 'music':
        print(restore_music())
    elif mode == 'control':
        print(restore_control())
    elif mode == 'tui':
        tui()
    else:
        raise SystemExit('Unknown mode')
