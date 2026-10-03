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


if __name__ == "__main__":
    unittest.main(verbosity=2)
