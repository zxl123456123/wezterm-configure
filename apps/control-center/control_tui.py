"""Compact Zellij control panel: workspace dispatch and background selection."""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(r'D:\terminal-workbench\apps\spectrum-venv\Lib\site-packages')))

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.geometry import Offset
from textual.widgets import Select, Static
from control_center import get_appearance, image_names, run_glaze, save_appearance, workspace_state


class Program(Static):
    can_focus = True

    def __init__(self, data):
        self.data = data
        self.start = None
        name = data.get('processName') or '未知程序'
        tone = sum(map(ord, name)) % 6
        super().__init__('  ◆  ' + name, classes=f'program tone-{tone}', markup=False)

    def on_mouse_down(self, event):
        if event.button == 1:
            self.start = event.screen_offset
            self.app._dragging = True
            self.capture_mouse()
            event.stop()

    def on_mouse_up(self, event):
        if self.start is None:
            return
        start, self.start = self.start, None
        self.app._dragging = False
        self.release_mouse()
        if self.app._refresh_requested:
            self.app.action_refresh()
        if start == event.screen_offset:
            self.app.operate_program('focus', self.data)
        else:
            self.app.drop_program(self.data, event.screen_offset)
        event.stop()


class WorkspaceCard(Vertical):
    def __init__(self, data):
        self.data = data
        classes = 'workspace-card active' if data.get('isDisplayed') else 'workspace-card'
        super().__init__(classes=classes)

    def compose(self):
        mark = '●' if self.data.get('isDisplayed') else '○'
        yield Static(f'  {mark}  {self.data["displayName"]}  ·  {self.data["monitor"]}',
                     classes='workspace-title', markup=False)
        with Vertical(classes='workspace-apps'):
            if self.data['windows']:
                for win in self.data['windows']:
                    yield Program(win)
            else:
                yield Static('  空工作区', classes='empty-card')


class Control(App):
    CSS = """
    Screen { background: #1e2030; color: #cad3f5; }
    #toolbar { height: 4; padding: 0 2; background: #24273a; }
    #title { width: 1fr; height: 3; content-align: left middle;
             color: #c6a0f6; text-style: bold; }
    #image-label { width: 7; height: 3; content-align: right middle;
                   color: #8bd5ca; text-style: bold; }
    #image { width: 38; margin: 0 0 0 1; }
    #overview { height: 3; margin: 1 2; padding: 0 2;
                background: #363a4f; color: #8bd5ca; text-style: bold;
                border: round #8bd5ca; }
    #board { height: 1fr; padding: 0 1; }
    .board-row { height: auto; min-height: 8; margin-bottom: 1; }
    .workspace-card { width: 1fr; height: auto; min-height: 8; margin: 0 1;
                      border: round #8087a2; background: #2b2e43; }
    .workspace-card.active { border: round #a6da95; }
    .workspace-card.active .workspace-title { color: #a6da95; }
    .workspace-card:hover { border: round #f5bde6; background: #32364d; }
    .workspace-title { height: 3; padding: 1 1; background: #3b4059;
                       color: #b7bdf8; text-style: bold; }
    .workspace-apps { height: auto; padding: 0 1 1 1; }
    .program { height: 1; margin: 1 0 0 0; background: #363a4f;
               padding: 0 1; text-style: bold; }
    .program:hover { background: #5b6078; color: #ffffff; }
    .tone-0 { color: #91d7e3; } .tone-1 { color: #a6da95; }
    .tone-2 { color: #f5bde6; } .tone-3 { color: #eed49f; }
    .tone-4 { color: #c6a0f6; } .tone-5 { color: #f5a97f; }
    .empty-card { color: #b8c0e0; padding: 1; }
    .offline { height: 6; margin: 1 2; padding: 1 2;
               background: #363a4f; color: #eed49f; border: round #eed49f; }
    """
    BINDINGS = [('r', 'refresh', '刷新')]

    def compose(self) -> ComposeResult:
        cfg = get_appearance()
        images = ['none', *image_names()]
        with Horizontal(id='toolbar'):
            yield Static('◈  工作台   /   程序调度', id='title')
            yield Static('背景', id='image-label')
            yield Select([(n if n != 'none' else '无背景', n) for n in images],
                         value=cfg['image'] if cfg['image'] in images else 'none',
                         allow_blank=False, id='image')
        yield Static('正在读取工作区…', id='overview')
        yield VerticalScroll(id='board')

    def on_mount(self):
        self._dragging = False
        self._refresh_pending = False
        # A single remembered user request; timer ticks never enqueue work.
        self._refresh_requested = False
        self._operation_pending = False
        self._last_signature = None
        self.action_refresh()
        self.set_interval(8, lambda: self.action_refresh(queue_if_busy=False))

    def message(self, content):
        self.query_one('#overview', Static).update('  ' + content)

    def action_refresh(self, queue_if_busy=True):
        if self._dragging or self._refresh_pending:
            if queue_if_busy:
                self._refresh_requested = True
            return
        self._refresh_pending = True
        self._refresh_requested = False
        self.run_worker(self._refresh_async())

    async def _refresh_async(self):
        cancelled = False
        try:
            try:
                groups = await asyncio.to_thread(workspace_state)
            except Exception:
                signature = ('offline',)
                message = '平铺管理尚未运行'
                rows = [Static('启动桌面工作台后，这里会显示可拖动的程序卡片。',
                               classes='offline', markup=False)]
            else:
                signature = tuple(
                    (group['name'], group['displayName'], group['monitor'],
                     group['isDisplayed'],
                     tuple((win['id'], win.get('processName') or '未知程序')
                           for win in group['windows']))
                    for group in groups
                )
                windows = sum(len(group['windows']) for group in groups)
                monitors = len({group['monitor'] for group in groups})
                message = (f'{monitors} 台显示器    {len(groups)} 个工作区    '
                           f'{windows} 个程序    ·    拖动程序卡片')

            if self._dragging:
                self._refresh_requested = True
                return
            if signature == self._last_signature:
                return
            if signature != ('offline',):
                rows = [Horizontal(*(WorkspaceCard(group) for group in groups[index:index+2]),
                                   classes='board-row')
                        for index in range(0, len(groups), 2)]
            board = self.query_one('#board', VerticalScroll)
            scroll_y = board.scroll_y
            # A failed or cancelled DOM update must not mark this snapshot committed.
            self._last_signature = None
            self.message(message)
            async with board.batch():
                await board.remove_children()
                if rows:
                    await board.mount(*rows)
            self.call_after_refresh(lambda: board.scroll_to(y=scroll_y, animate=False))
            self._last_signature = signature
        except asyncio.CancelledError:
            cancelled = True
            raise
        except Exception:
            self._last_signature = None
            self.message('刷新失败，请重试')
        finally:
            self._refresh_pending = False
            if not cancelled and self._refresh_requested and not self._dragging:
                self.action_refresh()

    def drop_program(self, program, point):
        for target in self.query(WorkspaceCard):
            if target.region.contains_point(Offset(int(point.x), int(point.y))):
                self.operate_program('move', program, target.data)
                return
        self.message('没有放到工作区，位置未改变')

    def operate_program(self, action, program, target=None):
        if self._operation_pending:
            self.message('上一个调度操作尚未完成')
            return
        self._operation_pending = True
        self.run_worker(self._operate_async(action, program, target))

    async def _operate_async(self, action, program, target):
        try:
            await asyncio.to_thread(run_glaze, action, program['id'],
                                    target['name'] if target else None)
            self.action_refresh()
            if target:
                self.message(f'{program.get("processName") or "程序"} → {target["displayName"]}')
            else:
                self.message('已聚焦 ' + (program.get('processName') or '程序'))
        except Exception as exc:
            self.message('操作失败：' + str(exc)[:70])
        finally:
            self._operation_pending = False

    def on_select_changed(self, event):
        if event.select.id != 'image' or event.value is Select.BLANK:
            return
        if event.value == get_appearance()['image']:
            return
        try:
            save_appearance({'image': event.value})
            self.message('背景已切换为 ' + str(event.value))
        except Exception as exc:
            self.message('切换背景失败：' + str(exc)[:70])


if __name__ == '__main__':
    Control().run()
