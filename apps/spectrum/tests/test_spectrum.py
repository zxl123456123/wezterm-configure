import importlib.util
import io
import os
from pathlib import Path
import re
import types
import tempfile
import unittest
import warnings
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('spectrum', ROOT / 'spectrum.py')
spectrum = importlib.util.module_from_spec(spec)
spec.loader.exec_module(spectrum)
np = spectrum.np
ANSI = re.compile(r'\x1b\[[0-9;?]*[A-Za-z]')


class Output(io.StringIO):
    def __init__(self, clock):
        super().__init__()
        self.clock = clock
        self.frames = []

    def write(self, value):
        if '\x1b[K' in value:
            self.frames.append((self.clock.now, value))
        return super().write(value)


class Recorder:
    def __init__(self, chunks, step=0.01):
        self.chunks = chunks
        self.step = step
        self.now = 0
        self.index = 0
        self.requests = []

    def record(self, numframes):
        self.requests.append(numframes)
        chunk = self.chunks[self.index]
        self.index += 1
        self.now += self.step
        return chunk


def exercise(chunks, step=0.01, size=lambda: (100, 8)):
    recorder = Recorder(chunks, step)
    output = Output(recorder)
    state = spectrum.SpectrumState()
    with patch.object(spectrum, 'SpectrumState', return_value=state):
        result = spectrum.main(recorder, clock=lambda: recorder.now, size=size,
                               output=output, should_run=lambda: recorder.index < len(chunks), sleep=lambda _: None)
    return result, recorder, output, state


class GeometryTests(unittest.TestCase):
    def test_geometry_matrix(self):
        for width, height in [(12, 4), (1, 1), (60, 5), (237, 8)]:
            if os.environ.get('SPECTRUM_LEGACY'):
                source = (ROOT / 'spectrum.py.original').read_text(encoding='utf-8')
                legacy = types.ModuleType('legacy')
                legacy.__file__ = str(ROOT / 'spectrum.py.original')
                recorder = types.SimpleNamespace(record=lambda **kw: np.ones((2048, 2)))
                context = unittest.mock.MagicMock()
                context.__enter__.return_value = recorder
                audio = types.SimpleNamespace(default_speaker=lambda: types.SimpleNamespace(id='fake'),
                    get_microphone=lambda **kw: types.SimpleNamespace(recorder=lambda **kw: context))
                with patch.dict('sys.modules', {'soundcard': audio}):
                    exec(compile(source, legacy.__file__, 'exec'), legacy.__dict__)
                output = io.StringIO()
                with patch.object(legacy.os, 'get_terminal_size', return_value=(width, height)), \
                     patch.object(legacy.signal, 'signal'), patch.object(legacy.sys, 'stdout', output), \
                     patch.object(legacy.time, 'sleep', side_effect=lambda _: setattr(legacy, 'running', False)):
                    legacy.main()
                lines = ANSI.sub('', output.getvalue()).splitlines()
                self.assertLessEqual(len(lines[1]), width - 1, ('legacy bar overflow', width, lines[1]))
            else:
                state = spectrum.SpectrumState()
                state.levels[:] = 2.4
                state.peaks[:] = 3.1
                state.amount = 1
                frame = spectrum.render_frame(state, width, height, 2, True, True)
                self.assertFalse(frame.endswith('\n'))
                lines = [ANSI.sub('', line) for line in re.split(r'\x1b\[\d+;1H', frame)[1:]]
            self.assertLessEqual(len(lines), height, (width, height, lines))
            for line in lines:
                self.assertLessEqual(len(line), width - 1, (width, height, line))
        self.assertEqual(spectrum.geometry(60, 5)[1], 11)
        self.assertEqual(spectrum.geometry(237, 8)[1], 24)


class MainLoopTests(unittest.TestCase):
    def test_empty_and_latest_bounded_window(self):
        _, recorder, output, state = exercise([np.empty((0, 2)), np.ones((3000, 2)),
                                               np.full((6000, 2), 2.0)])
        self.assertEqual(state.window.size, 2048)
        np.testing.assert_array_equal(state.window, np.full(2048, 2.0))
        self.assertTrue(all(request is None for request in recorder.requests))
        self.assertIn('\x1b[?25h\x1b[?1049l', output.getvalue())

    def test_main_resize_and_audio_wakeups_with_bounded_each_capture(self):
        recorder = Recorder([np.zeros(100)] * 40 + [np.ones(5000) * 0.1] * 20)
        output = Output(recorder)
        state = spectrum.SpectrumState()
        sizes = []
        original_capture = state.capture

        def capture(samples):
            result = original_capture(samples)
            sizes.append(state.window.size)
            return result

        state.capture = capture
        with patch.object(spectrum, 'SpectrumState', return_value=state), \
             patch.object(np.fft, 'rfft', wraps=np.fft.rfft) as fft:
            spectrum.main(recorder, clock=lambda: recorder.now, output=output,
                          size=lambda: (12, 4) if recorder.index < 20 else (60, 5),
                          should_run=lambda: recorder.index < len(recorder.chunks))
        self.assertLessEqual(max(sizes), 2048)
        self.assertEqual(len([t for t, _ in output.frames if t <= 0.4 + 1e-9]), 2)
        self.assertGreater(fft.call_count, 0)
        self.assertTrue(any(t > 0.4 for t, _ in output.frames))

    def test_known_warning_is_bounded_and_not_on_terminal(self):
        class SoundcardRuntimeWarning(RuntimeWarning):
            pass

        class WarningRecorder(Recorder):
            def record(self, numframes):
                warnings.warn('data discontinuity in recording', SoundcardRuntimeWarning)
                return super().record(numframes)

        recorder = WarningRecorder([np.zeros(2048)] * 800)
        output = Output(recorder)
        error = io.StringIO()
        with tempfile.TemporaryDirectory(prefix='workbench-warning-') as temporary, \
             patch.object(spectrum, '__file__', str(Path(temporary) / 'spectrum.py')), \
             patch('sys.stderr', error):
            with warnings.catch_warnings():
                warnings.simplefilter('always')
                spectrum.main(recorder, clock=lambda: recorder.now, output=output,
                              size=lambda: (12, 4), should_run=lambda: recorder.index < 800)
            logs = list(Path(temporary).glob('*.log*'))
            self.assertGreater(len(logs), 0)
            self.assertLessEqual(len(logs), 2)
            self.assertLessEqual(sum(path.stat().st_size for path in logs), 32768)
        self.assertEqual(error.getvalue(), '')
        self.assertNotIn('discontinuity', output.getvalue())

    def test_silence_settles_and_stays_without_fft_trig_or_output(self):
        signal = np.sin(np.arange(2048) * 0.1) * 0.1
        chunks = [signal] * 30 + [np.zeros(2048)] * 600
        with patch.object(np.fft, 'rfft', wraps=np.fft.rfft) as fft, \
             patch.object(np, 'sin', wraps=np.sin) as sin, patch.object(np, 'cos', wraps=np.cos) as cos:
            _, _, output, state = exercise(chunks)
            counts = fft.call_count, sin.call_count, cos.call_count
            frames = len(output.frames)
            recorder = Recorder([np.zeros(2048)] * 100)
            recorder.now = 10
            with patch.object(spectrum, 'SpectrumState', return_value=state):
                spectrum.main(recorder, clock=lambda: recorder.now, output=output,
                              size=lambda: (100, 8), should_run=lambda: recorder.index < 100)
            self.assertEqual(counts, (fft.call_count, sin.call_count, cos.call_count))
            self.assertEqual(frames, len(output.frames))
        self.assertEqual(state.amount, 0)
        self.assertFalse(np.any(state.peaks))
        quiet_times = [t for t, _ in output.frames if t >= 0.31]
        self.assertTrue(all(b - a >= 0.25 - 1e-9 for a, b in zip(quiet_times, quiet_times[1:])))

    def test_sound_then_empty_settles_and_yields_in_main(self):
        chunks = [np.sin(np.arange(2048) * 0.1) * 0.1] * 30 + [np.empty((0, 2))] * 800
        with patch.object(np.fft, 'rfft', wraps=np.fft.rfft) as fft, \
             patch.object(np, 'sin', wraps=np.sin) as sin, patch.object(np, 'cos', wraps=np.cos) as cos:
            recorder = Recorder(chunks)
            state = spectrum.SpectrumState()
            output = Output(recorder)
            sleep = unittest.mock.Mock()
            with patch.object(spectrum, 'SpectrumState', return_value=state):
                spectrum.main(recorder, clock=lambda: recorder.now, size=lambda: (100, 8),
                              output=output, sleep=sleep, should_run=lambda: recorder.index < len(chunks))
            self.assertEqual(sleep.call_count, 800)
            sleep.assert_called_with(0.005)
            self.assertEqual(state.window.size, 0)
            self.assertEqual(state.amount, 0)
            self.assertFalse(np.any(state.peaks))
            self.assertTrue(all(t < 5 for t, _ in output.frames))
            self.assertLessEqual(fft.call_count, 6)
            counts = fft.call_count, sin.call_count, cos.call_count
            frame_count = len(output.frames)
            recorder = Recorder([np.empty((0, 2))] * 100)
            recorder.now = 10
            with patch.object(spectrum, 'SpectrumState', return_value=state):
                spectrum.main(recorder, clock=lambda: recorder.now, size=lambda: (100, 8),
                              output=output, sleep=sleep, should_run=lambda: recorder.index < 100)
            self.assertEqual(counts, (fft.call_count, sin.call_count, cos.call_count))
            self.assertEqual(frame_count, len(output.frames))

    def test_active_frame_cap_and_resize_wakeup(self):
        _, _, output, state = exercise([np.ones(2048) * 0.1] * 100)
        times = [t for t, _ in output.frames]
        self.assertLessEqual(len(times), 20)
        self.assertTrue(all(b - a >= 0.05 - 1e-9 for a, b in zip(times, times[1:])))
        state = spectrum.SpectrumState()
        self.assertIsNotNone(state.frame(0, (100, 8)))
        self.assertIsNone(state.frame(1, (100, 8)))
        with patch.object(np.fft, 'rfft', wraps=np.fft.rfft) as fft:
            self.assertIn('\x1b[2J', state.frame(1.1, (12, 4)))
            self.assertEqual(fft.call_count, 0)
            state.capture(np.ones(2048) * 0.1)
            self.assertIsNotNone(state.frame(1.2, (12, 4)))
            self.assertEqual(fft.call_count, 1)

    def test_record_failure_restores_terminal_and_propagates(self):
        output = io.StringIO()
        recorder = unittest.mock.Mock()
        recorder.record.side_effect = RuntimeError('fake device failed')
        with self.assertRaisesRegex(RuntimeError, 'fake device failed'):
            spectrum.main(recorder, output=output, should_run=lambda: True)
        self.assertTrue(output.getvalue().endswith('\x1b[0m\x1b[?25h\x1b[?1049l'))


if __name__ == '__main__':
    unittest.main()
