"""All-mock, headless Control behavior checks. Never imports the real backend."""

import argparse
import asyncio
import copy
import importlib.util
import os
from pathlib import Path
import sys
import threading
import types
import unittest
from unittest.mock import Mock, patch


ROOT = Path(r"D:\terminal-workbench")
DEFAULT_SOURCE = ROOT / "updates/workbench-usability-20261003/control_tui.py"
parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
parser.add_argument("--test", help="Run one ControlTests method")
args, remaining = parser.parse_known_args()
SOURCE = args.source.resolve(strict=True)
sys.argv = [sys.argv[0], *( [f"ControlTests.{args.test}"] if args.test else []), *remaining]
print(f"SOURCE={SOURCE}", flush=True)


def state(name="Code", display="Code", monitor="Display 1", shown=True,
          windows=None):
    if windows is None:
        windows = [{"id": "w1", "processName": "Editor", "hasFocus": True,
                    "title": "T", "state": "normal"}]
    return [{"name": name, "displayName": display, "monitor": monitor,
             "isDisplayed": shown, "windows": windows}]


class ControlTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.current = state()
        backend = types.ModuleType("control_center")
        backend.get_appearance = Mock(return_value={"image": "none"})
        backend.image_names = Mock(return_value=[])
        backend.workspace_state = Mock(side_effect=lambda: copy.deepcopy(self.current))
        backend.run_glaze = Mock()
        backend.save_appearance = Mock()
        self.backend = backend
        self.module_patch = patch.dict(sys.modules, {"control_center": backend})
        self.module_patch.start()
        spec = importlib.util.spec_from_file_location("isolated_control", SOURCE)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def tearDown(self):
        self.module_patch.stop()
        self.backend.save_appearance.assert_not_called()

    async def until(self, pilot, predicate):
        for _ in range(160):
            await pilot.pause()
            if predicate():
                return
            await asyncio.sleep(0.01)
        self.fail("timed out waiting for headless worker")

    async def refresh(self, app, pilot):
        before = self.backend.workspace_state.call_count
        app.action_refresh()
        await self.until(pilot, lambda: self.backend.workspace_state.call_count > before and
                         not app._refresh_pending)
        await pilot.pause()

    async def test_c1_c2_signature_and_identity(self):
        app = self.module.Control()
        async with app.run_test(size=(100, 30)) as pilot:
            await self.until(pilot, lambda: len(app.query(self.module.WorkspaceCard)) == 1)
            card = app.query_one(self.module.WorkspaceCard)
            original_init = self.module.WorkspaceCard.__init__
            constructed = []

            def count_init(widget, data):
                constructed.append(data)
                original_init(widget, data)

            with patch.object(self.module.WorkspaceCard, "__init__", count_init):
                await self.refresh(app, pilot)
            self.assertEqual(constructed, [])
            self.assertIs(app.query_one(self.module.WorkspaceCard), card)
            self.current = state(display="Renamed")
            await self.refresh(app, pilot)
            card = app.query_one(self.module.WorkspaceCard)
            self.assertIn("Renamed", str(app.query_one(".workspace-title").render()))
            self.current[0]["windows"][0].update(hasFocus=False, title="Other", state="minimized")
            await self.refresh(app, pilot)
            self.assertIs(app.query_one(self.module.WorkspaceCard), card)
            for changed in (
                state(display="Renamed", monitor="Display 2"),
                state(display="Renamed", monitor="Display 2", shown=False),
                state(display="Renamed", monitor="Display 2", shown=False,
                      windows=[{"id": "w1", "processName": "Browser"}]),
                state(name="other", display="Renamed", monitor="Display 2", shown=False,
                      windows=[{"id": "w1", "processName": "Browser"}]),
                state(name="other", display="Renamed", monitor="Display 2", shown=False,
                      windows=[{"id": "w2", "processName": "Browser"}]),
                state(name="other", display="Renamed", monitor="Display 2", shown=False,
                      windows=[{"id": "w2", "processName": "Browser"},
                               {"id": "w3", "processName": None}]),
            ):
                self.current = changed
                old = app.query_one(self.module.WorkspaceCard)
                await self.refresh(app, pilot)
                self.assertIsNot(app.query_one(self.module.WorkspaceCard), old)
            self.assertEqual(app.query_one(self.module.WorkspaceCard).data["name"], "other")
            self.assertEqual([p.data["id"] for p in app.query(self.module.Program)], ["w2", "w3"])
            self.assertIn("未知程序", str(list(app.query(self.module.Program))[1].render()))
            self.current[0]["windows"].reverse()
            old = app.query_one(self.module.WorkspaceCard)
            await self.refresh(app, pilot)
            self.assertIsNot(app.query_one(self.module.WorkspaceCard), old)
            self.assertEqual([p.data["id"] for p in app.query(self.module.Program)], ["w3", "w2"])

    async def test_c3_c5_busy_timer_and_coalescing(self):
        app = self.module.Control()
        async with app.run_test(size=(100, 30)) as pilot:
            await self.until(pilot, lambda: len(app.query(self.module.WorkspaceCard)) == 1)
            board = app.query_one("#board")
            original = board.remove_children
            entered, release = asyncio.Event(), asyncio.Event()

            async def stalled(*a, **kw):
                entered.set()
                await release.wait()
                return await original(*a, **kw)

            board.remove_children = stalled
            self.current = state(display="X")
            app.action_refresh()
            await self.until(pilot, entered.is_set)
            count = self.backend.workspace_state.call_count
            self.current = state(display="Y")
            app.action_refresh(queue_if_busy=False)
            await pilot.pause()
            self.assertEqual(self.backend.workspace_state.call_count, count)
            app.action_refresh()
            app.action_refresh()
            await pilot.pause()
            self.assertEqual(self.backend.workspace_state.call_count, count)
            release.set()
            await self.until(pilot, lambda: self.backend.workspace_state.call_count == count + 1
                             and any("Y" in str(title.render())
                                     for title in app.query(".workspace-title")))
            self.assertEqual(self.backend.workspace_state.call_count, count + 1)

    async def test_c4_operation_during_slow_query(self):
        app = self.module.Control()
        async with app.run_test(size=(100, 30)) as pilot:
            await self.until(pilot, lambda: len(app.query(self.module.WorkspaceCard)) == 1)
            entered, release = threading.Event(), threading.Event()
            calls = 0

            def slow():
                nonlocal calls
                calls += 1
                if calls == 1:
                    entered.set()
                    release.wait(3)
                    return state(display="Before")
                return state(display="After")

            self.backend.workspace_state.side_effect = slow
            app.action_refresh()
            await self.until(pilot, entered.is_set)
            app.operate_program("focus", {"id": "w1", "processName": "Editor"})
            await self.until(pilot, lambda: not app._operation_pending)
            self.backend.run_glaze.assert_called_once_with("focus", "w1", None)
            release.set()
            await self.until(pilot, lambda: calls >= 2 and
                             any("After" in str(title.render())
                                 for title in app.query(".workspace-title")))
            self.assertEqual(calls, 2)
            self.assertFalse(app._operation_pending)

    async def test_c5_drag_release_only_when_queued(self):
        app = self.module.Control()
        async with app.run_test(size=(100, 30)) as pilot:
            await self.until(pilot, lambda: len(app.query(self.module.Program)) == 1)
            program = app.query_one(self.module.Program)
            initial = self.backend.workspace_state.call_count
            app._dragging = True
            app.action_refresh(queue_if_busy=False)
            self.assertEqual(self.backend.workspace_state.call_count, initial)
            app.action_refresh()
            self.current = state(display="Drag")
            event = types.SimpleNamespace(screen_offset=types.SimpleNamespace(x=1, y=1),
                                          stop=lambda: None)
            program.start = event.screen_offset
            program.release_mouse = Mock()
            app.operate_program = Mock()
            program.on_mouse_up(event)
            await self.until(pilot, lambda: "Drag" in str(app.query_one(".workspace-title").render()))
            self.assertEqual(self.backend.workspace_state.call_count, initial + 1)
            app.operate_program.assert_called_once()
            next_count = self.backend.workspace_state.call_count
            program = app.query_one(self.module.Program)
            program.start = event.screen_offset
            program.release_mouse = Mock()
            program.on_mouse_up(event)
            await pilot.pause()
            self.assertEqual(self.backend.workspace_state.call_count, next_count)

    async def test_c6_offline_and_dom_failure_recovery(self):
        app = self.module.Control()
        async with app.run_test(size=(100, 30)) as pilot:
            await self.until(pilot, lambda: len(app.query(self.module.WorkspaceCard)) == 1)
            self.backend.workspace_state.side_effect = RuntimeError("offline")
            await self.refresh(app, pilot)
            self.assertEqual(len(app.query(".offline")), 1)
            offline = app.query_one(".offline")
            await self.refresh(app, pilot)
            self.assertIs(app.query_one(".offline"), offline)
            self.backend.workspace_state.side_effect = lambda: state(display="Back")
            await self.refresh(app, pilot)
            self.assertIn("Back", str(app.query_one(".workspace-title").render()))
            board = app.query_one("#board")
            original = board.remove_children
            thrown = False

            async def fail_once(*a, **kw):
                nonlocal thrown
                if not thrown:
                    thrown = True
                    raise RuntimeError("DOM failed")
                return await original(*a, **kw)

            board.remove_children = fail_once
            self.backend.workspace_state.side_effect = lambda: state(display="Retry")
            await self.refresh(app, pilot)
            self.assertTrue(thrown)
            self.assertFalse(app._refresh_pending)
            await self.refresh(app, pilot)
            self.assertIn("Retry", str(app.query_one(".workspace-title").render()))
            board.remove_children = original
            original_mount = board.mount
            mount_thrown = False

            async def fail_mount(*a, **kw):
                nonlocal mount_thrown
                if not mount_thrown:
                    mount_thrown = True
                    raise RuntimeError("mount failed")
                return await original_mount(*a, **kw)

            board.mount = fail_mount
            self.backend.workspace_state.side_effect = lambda: state(display="After mount failure")
            await self.refresh(app, pilot)
            self.assertTrue(mount_thrown)
            self.assertFalse(app._refresh_pending)
            await self.refresh(app, pilot)
            self.assertIn("After mount failure", str(app.query_one(".workspace-title").render()))

    async def test_c7_cancel_during_mount_then_retry(self):
        app = self.module.Control()
        async with app.run_test(size=(100, 30)) as pilot:
            await self.until(pilot, lambda: len(app.query(self.module.WorkspaceCard)) == 1)
            board = app.query_one("#board")
            original = board.mount
            entered, release = asyncio.Event(), asyncio.Event()

            async def stalled(*a, **kw):
                entered.set()
                await release.wait()
                return await original(*a, **kw)

            board.mount = stalled
            self.backend.workspace_state.side_effect = lambda: state(display="Cancelled")
            app.action_refresh()
            await self.until(pilot, entered.is_set)
            count = self.backend.workspace_state.call_count
            app.action_refresh(queue_if_busy=False)
            app.action_refresh()
            app.action_refresh()
            await pilot.pause()
            self.assertEqual(self.backend.workspace_state.call_count, count)
            workers = list(app.workers)
            for worker in workers:
                worker.cancel()
            release.set()
            await self.until(pilot, lambda: not app._refresh_pending)
            await pilot.pause()
            self.assertEqual(self.backend.workspace_state.call_count, count)
            self.assertNotIn("平铺管理尚未运行", str(app.query_one("#overview").render()))
            self.assertEqual(len(app.query(self.module.WorkspaceCard)), 0)
            board.mount = original
            await self.refresh(app, pilot)
            self.assertIn("Cancelled", str(app.query_one(".workspace-title").render()))

    async def test_c7_cancelled_query_thread_boundary(self):
        app = self.module.Control()
        async with app.run_test(size=(100, 30)) as pilot:
            await self.until(pilot, lambda: len(app.query(self.module.WorkspaceCard)) == 1)
            entered, release, exited = threading.Event(), threading.Event(), threading.Event()

            def slow():
                entered.set()
                release.wait(3)
                exited.set()
                return state(display="Old thread result")

            self.backend.workspace_state.side_effect = slow
            app.action_refresh()
            await self.until(pilot, entered.is_set)
            for worker in list(app.workers):
                worker.cancel()
            await self.until(pilot, lambda: not app._refresh_pending)
            self.assertFalse(exited.is_set())  # asyncio cancellation did not stop to_thread.
            self.assertEqual(len(app.query(self.module.WorkspaceCard)), 1)
            release.set()
            await self.until(pilot, exited.is_set)
            self.backend.workspace_state.side_effect = lambda: state(display="New query")
            await self.refresh(app, pilot)
            self.assertIn("New query", str(app.query_one(".workspace-title").render()))

    async def test_c8_c9_operation_failure_and_preserved_ui(self):
        app = self.module.Control()
        async with app.run_test(size=(100, 30)) as pilot:
            await self.until(pilot, lambda: len(app.query(self.module.WorkspaceCard)) == 1)
            self.assertIn("background: #1e2030", app.CSS)
            self.assertIn(("r", "refresh", "刷新"), app.BINDINGS)
            self.backend.run_glaze.side_effect = RuntimeError("mock failure")
            app.operate_program("focus", {"id": "w1", "processName": "Editor"})
            app.operate_program("focus", {"id": "w2", "processName": "Other"})
            await self.until(pilot, lambda: not app._operation_pending)
            self.backend.run_glaze.assert_called_once()
            self.assertIn("操作失败", str(app.query_one("#overview").render()))
            await self.refresh(app, pilot)
            self.backend.run_glaze.side_effect = None
            app.operate_program("move", {"id": "w1", "processName": "Editor"},
                                {"name": "2", "displayName": "Other"})
            await self.until(pilot, lambda: not app._operation_pending)
            self.backend.run_glaze.assert_called_with("move", "w1", "2")
            self.assertIn("Editor → Other", str(app.query_one("#overview").render()))
            board = app.query_one("#board")
            saved_y = board.scroll_y
            with patch.object(app, "call_after_refresh") as after_refresh:
                self.current = state(display="Scrolled")
                await self.refresh(app, pilot)
            after_refresh.assert_called()
            with patch.object(board, "scroll_to") as scroll_to:
                after_refresh.call_args.args[0]()
            scroll_to.assert_called_once_with(y=saved_y, animate=False)


class ControlLayoutTests(unittest.IsolatedAsyncioTestCase):
    sizes = [(100, 30), (60, 20), (40, 16)]

    def setUp(self):
        names = ["ExampleDevelopmentApplicationLongName", "长中文程序名称用于窄窗折行验收", None]
        self.current = [state(name=f"ws{i}", display=f"W{i}", monitor=f"M{i % 2}",
                              shown=i == 0, windows=[{"id": f"p{i}", "processName": name}])[0]
                        for i, name in enumerate(names)]
        self.current += state(name="ws3", display="W3", monitor="M1", shown=False, windows=[])
        self.appearance = {"image": "none"}
        backend = types.ModuleType("control_center")
        backend.get_appearance = Mock(side_effect=lambda: dict(self.appearance))
        backend.image_names = Mock(return_value=["example.png"])
        backend.workspace_state = Mock(side_effect=lambda: copy.deepcopy(self.current))
        backend.run_glaze = Mock()
        backend.save_appearance = Mock(side_effect=lambda change: self.appearance.update(change))
        self.backend = backend
        self.module_patch = patch.dict(sys.modules, {"control_center": backend})
        self.module_patch.start()
        spec = importlib.util.spec_from_file_location("isolated_control_layout", SOURCE)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def tearDown(self):
        self.module_patch.stop()

    async def until(self, pilot, predicate):
        for _ in range(160):
            await pilot.pause()
            if predicate():
                return
            await asyncio.sleep(0.01)
        self.fail("timed out waiting for headless layout worker")

    async def ready(self, app, pilot):
        await self.until(pilot, lambda: len(app.query(self.module.WorkspaceCard)) == 4
                         and not app._refresh_pending)
        await pilot.pause()
        self.backend.save_appearance.assert_not_called()

    def lines(self, widget):
        from textual.geometry import Region
        return [strip.text.strip("│╭╮╰╯─") for strip in widget.render_lines(
            Region(0, 0, widget.region.width, widget.region.height))]

    def assert_text(self, widget, text):
        self.assertEqual(widget.region.intersection(widget.app.screen.region), widget.region)
        self.assertIn("".join(text.split()), "".join("".join(self.lines(widget)).split()))

    async def read_board(self, app, pilot):
        board = app.query_one("#board")
        widgets = list(app.query(".workspace-title, .program, .empty-card, .offline"))
        visible = {widget: {} for widget in widgets}
        step = max(1, board.content_region.height)
        positions = [*range(0, int(board.max_scroll_y) + 1, step), int(board.max_scroll_y)]
        for position in positions:
            board.scroll_to(y=position, animate=False)
            await pilot.pause()
            for widget in widgets:
                clip = widget.region.intersection(board.content_region).intersection(app.screen.region)
                if clip:
                    self.assertGreaterEqual(widget.region.x, board.content_region.x)
                    self.assertLessEqual(widget.region.right, board.content_region.right)
                    for row in range(clip.y - widget.region.y, clip.bottom - widget.region.y):
                        visible[widget][row] = self.lines(widget)[row]
        for widget, rows in visible.items():
            self.assertEqual(len(rows), widget.region.height, (widget, rows))
            self.assertIn("".join(str(widget.render()).split()),
                          "".join("".join(rows[row] for row in sorted(rows)).split()))
        return positions

    async def reveal(self, app, pilot, widget):
        board = app.query_one("#board")
        board.scroll_to(y=board.scroll_y + widget.region.y - board.content_region.y, animate=False)
        await pilot.pause()
        clip = widget.region.intersection(board.content_region).intersection(app.screen.region)
        self.assertTrue(clip, widget)
        return self.module.Offset(clip.x + min(1, clip.width - 1), clip.y)

    def mouse(self, point):
        return types.SimpleNamespace(button=1, screen_offset=point, stop=Mock())

    async def test_layout_matrix_rendered_names_and_scroll(self):
        for size in self.sizes:
            with self.subTest(size=size):
                app = self.module.Control()
                async with app.run_test(size=size) as pilot:
                    await self.ready(app, pilot)
                    image = app.query_one("#image")
                    self.assertEqual(image.region.intersection(app.screen.region), image.region)
                    arrow = app.query_one("#image .down-arrow")
                    self.assertEqual(arrow.region.intersection(app.screen.region), arrow.region)
                    self.assert_text(app.query_one("#title"), "◈  工作台   /   程序调度")
                    self.assert_text(app.query_one("#image-label"), "背景")
                    self.assertGreater(app.query_one("#board").content_region.height, 0)
                    positions = await self.read_board(app, pilot)
                    self.assert_text(app.query_one("#overview"), "2 台显示器    4 个工作区    3 个程序    ·    拖动程序卡片")
                    print(f"LAYOUT size={size} select={image.region} board={app.query_one('#board').content_region} scroll={positions}")
        app = self.module.Control()
        async with app.run_test(size=(24, 12)) as pilot:
            await self.ready(app, pilot)
            print(f"OBSERVATION size=(24, 12) select={app.query_one('#image').region} board={app.query_one('#board').content_region}")

    async def test_select_matrix_success_none_and_failure(self):
        for size in self.sizes:
            with self.subTest(size=size):
                self.appearance["image"] = "none"
                self.backend.save_appearance.reset_mock(side_effect=True)
                self.backend.save_appearance.side_effect = lambda change: self.appearance.update(change)
                app = self.module.Control()
                async with app.run_test(size=size) as pilot:
                    await self.ready(app, pilot)
                    select = app.query_one("#image")
                    self.assertTrue(await pilot.click("#image .down-arrow"))
                    self.assertTrue(select.expanded)
                    popup = app.query_one("#image SelectOverlay")
                    self.assert_text(popup, "example.png")
                    self.assert_text(popup, "无背景")
                    await pilot.press("end", "enter")
                    await pilot.pause()
                    self.backend.save_appearance.assert_called_once_with({"image": "example.png"})
                    self.assert_text(app.query_one("#overview"), "背景已切换为 example.png")
                    self.assertTrue(await pilot.click("#image .down-arrow"))
                    await pilot.press("home", "enter")
                    await pilot.pause()
                    self.backend.save_appearance.assert_called_with({"image": "none"})
                    self.assertEqual(self.appearance["image"], "none")
                    self.assert_text(app.query_one("#overview"), "背景已切换为 none")
                    self.backend.save_appearance.side_effect = RuntimeError("synthetic background failure")
                    self.assertTrue(await pilot.click("#image .down-arrow"))
                    await pilot.press("end", "enter")
                    await pilot.pause()
                    self.assertEqual(self.appearance["image"], "none")
                    self.assert_text(app.query_one("#overview"), "切换背景失败：synthetic background failure")

    async def test_click_and_simulated_drag_matrix(self):
        for size in self.sizes:
            with self.subTest(size=size):
                self.backend.run_glaze.reset_mock()
                app = self.module.Control()
                async with app.run_test(size=size) as pilot:
                    await self.ready(app, pilot)
                    program = app.query_one(self.module.Program)
                    point = await self.reveal(app, pilot, program)
                    self.assertTrue(await pilot.click(program, offset=(point.x - program.region.x,
                                                                     point.y - program.region.y)))
                    await self.until(pilot, lambda: not app._operation_pending and not app._refresh_pending)
                    self.backend.run_glaze.assert_called_with("focus", "p0", None)
                    self.assert_text(app.query_one("#overview"), "已聚焦 ExampleDevelopmentApplicationLongName")
                    self.assertIs(app.query_one(self.module.Program), program)
                    with patch.object(program, "capture_mouse") as capture, patch.object(program, "release_mouse") as release:
                        program.on_mouse_down(self.mouse(point))
                        self.assertTrue(app._dragging)
                        target = list(app.query(self.module.WorkspaceCard))[-1]
                        target_point = await self.reveal(app, pilot, target)
                        program.on_mouse_up(self.mouse(target_point))
                        capture.assert_called_once()
                        release.assert_called_once()
                    await self.until(pilot, lambda: not app._operation_pending and not app._refresh_pending)
                    self.backend.run_glaze.assert_called_with("move", "p0", "ws3")
                    self.assertFalse(app._dragging)
                    self.assertIs(app.query_one(self.module.Program), program)
                    calls = self.backend.run_glaze.call_count
                    with patch.object(program, "capture_mouse"), patch.object(program, "release_mouse"):
                        program.on_mouse_down(self.mouse(target_point))
                        program.on_mouse_up(self.mouse(self.module.Offset(0, 0)))
                    await pilot.pause()
                    self.assertEqual(self.backend.run_glaze.call_count, calls)
                    self.assert_text(app.query_one("#overview"), "没有放到工作区，位置未改变")
                    point = await self.reveal(app, pilot, program)
                    if size[0] == 40:
                        self.assertGreater(program.region.height, 1)
                        point = self.module.Offset(point.x, point.y + 1)
                        with patch.object(program, "capture_mouse"), patch.object(program, "release_mouse"):
                            program.on_mouse_down(self.mouse(point))
                            program.on_mouse_up(self.mouse(point))
                        await self.until(pilot, lambda: not app._operation_pending)
                        self.backend.run_glaze.assert_called_with("focus", "p0", None)

    async def test_resize_identity_popup_and_drag_queue(self):
        app = self.module.Control()
        original_interval = app.set_interval
        control_timers = []

        def paused_interval(interval, callback=None, **kwargs):
            timer = original_interval(interval, callback, **kwargs)
            if interval == 8:
                timer.pause()  # Isolate only this app's scheduled backend refresh.
                control_timers.append((interval, timer))
            return timer

        app.set_interval = paused_interval
        async with app.run_test(size=(100, 30)) as pilot:
            await self.ready(app, pilot)
            self.assertEqual([interval for interval, timer in control_timers], [8])
            self.assertIs(control_timers[0][1].target, app)
            identity = list(app.query(".board-row, .workspace-card, .program"))
            select = app.query_one("#image")
            self.assertTrue(await pilot.click("#image .down-arrow"))
            await pilot.press("escape")
            await pilot.pause()
            symbols = ("workspace_state", "run_glaze", "save_appearance", "get_appearance", "image_names")
            counts = [getattr(self.backend, name).call_count for name in symbols]
            clock = asyncio.get_running_loop().time
            measured = clock()
            await pilot.pause(8.2)
            elapsed = clock() - measured
            self.assertGreaterEqual(elapsed, 8)
            self.assertEqual([getattr(self.backend, name).call_count for name in symbols], counts)
            print(f"PAUSED_CONTROL_TIMER interval=8 elapsed={elapsed:.3f}s backend_delta=0 target=Control")
            for size in [(60, 20), (40, 16), (100, 30), (79, 30), (80, 30)]:
                await pilot.resize_terminal(*size)
                self.assertEqual(app.screen.has_class("compact"), size[0] < 80)
                self.assertEqual(list(app.query(".board-row, .workspace-card, .program")), identity)
                self.assertEqual([getattr(self.backend, name).call_count for name in symbols], counts)
            program = app.query_one(self.module.Program)
            point = await self.reveal(app, pilot, program)
            with patch.object(program, "capture_mouse"), patch.object(program, "release_mouse"):
                program.on_mouse_down(self.mouse(point))
                app.action_refresh()
                await pilot.resize_terminal(40, 16)
                self.assertEqual(self.backend.workspace_state.call_count, counts[0])
                self.assertTrue(app._refresh_requested)
                self.assertEqual(list(app.query(".board-row, .workspace-card, .program")), identity)
                target = list(app.query(self.module.WorkspaceCard))[1]
                target_point = await self.reveal(app, pilot, target)
                program.on_mouse_up(self.mouse(target_point))
            await self.until(pilot, lambda: not app._refresh_pending and not app._operation_pending)
            self.assertGreaterEqual(self.backend.workspace_state.call_count, counts[0] + 1)
            self.assertEqual(list(app.query(".board-row, .workspace-card, .program")), identity)
            self.backend.run_glaze.assert_called_once_with("move", "p0", "ws1")

    async def test_resize_during_same_data_slow_refresh(self):
        app = self.module.Control()
        async with app.run_test(size=(100, 30)) as pilot:
            await self.ready(app, pilot)
            identity = list(app.query(".board-row, .workspace-card, .program"))
            entered, release = threading.Event(), threading.Event()

            def slow():
                entered.set()
                release.wait(3)
                return copy.deepcopy(self.current)

            self.backend.workspace_state.side_effect = slow
            app.action_refresh()
            await self.until(pilot, entered.is_set)
            count = self.backend.workspace_state.call_count
            await pilot.resize_terminal(40, 16)
            self.assertTrue(app._refresh_pending)
            self.assertEqual(self.backend.workspace_state.call_count, count)
            self.assertEqual(list(app.query(".board-row, .workspace-card, .program")), identity)
            release.set()
            await self.until(pilot, lambda: not app._refresh_pending)
            self.assertEqual(list(app.query(".board-row, .workspace-card, .program")), identity)
            self.backend.run_glaze.assert_not_called()
            self.backend.save_appearance.assert_not_called()

    async def test_narrow_failure_offline_and_native_scroll(self):
        app = self.module.Control()
        async with app.run_test(size=(40, 16)) as pilot:
            await self.ready(app, pilot)
            self.backend.run_glaze.side_effect = RuntimeError("synthetic operation failure")
            app.operate_program("focus", {"id": "p0", "processName": "Example"})
            await self.until(pilot, lambda: not app._operation_pending)
            self.assert_text(app.query_one("#overview"), "操作失败：synthetic operation failure")
            self.backend.workspace_state.side_effect = RuntimeError("synthetic offline")
            app.action_refresh()
            await self.until(pilot, lambda: not app._refresh_pending and len(app.query(".offline")) == 1)
            self.assert_text(app.query_one("#overview"), "平铺管理尚未运行")
            await self.read_board(app, pilot)
            self.backend.workspace_state.side_effect = lambda: copy.deepcopy(self.current)
            app.action_refresh()
            await self.until(pilot, lambda: not app._refresh_pending and len(app.query(self.module.WorkspaceCard)) == 4)
            board = app.query_one("#board")
            board.focus()
            await pilot.press("end")
            await pilot.pause(0.4)
            self.assertEqual(board.scroll_y, board.max_scroll_y)
            self.assertIn(("r", "refresh", "刷新"), app.BINDINGS)
            for color in ("#1e2030", "#5b6078", "#a6da95", "#f5bde6", "#91d7e3", "#f5a97f"):
                self.assertIn(color, app.CSS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
