import importlib.util
import io
import os
from pathlib import Path
import re
import types
import tempfile
import unittest
import warnings
from contextlib import ExitStack, contextmanager
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


class ContinuityTests(unittest.TestCase):
    def test_short_empty_gap_keeps_window_and_does_not_draw_idle(self):
        state = spectrum.SpectrumState()
        tone = np.sin(np.arange(2048) * 0.1) * 0.1
        state.capture(tone)
        state.frame(0, (172, 6))
        state.capture(np.empty((0, 2)))
        with count_calls() as counts:
            self.assertIsNone(state.frame(0.06, (172, 6)))
            self.assertIsNone(state.frame(0.12, (172, 6)))
        np.testing.assert_array_equal(state.window, tone)
        self.assertEqual(counts['rfft'], 0)
        self.assertEqual(counts['render_frame'], 0)
        next_chunk = np.full(441, 0.02)
        state.capture(next_chunk)
        np.testing.assert_array_equal(state.window, np.concatenate((tone, next_chunk))[-2048:])
        self.assertIn('SYSTEM AUDIO', state.frame(0.13, (172, 6)))

    def test_long_empty_gap_expires_then_restarts_without_old_audio(self):
        state = spectrum.SpectrumState()
        state.capture(np.ones(2048) * 0.1)
        state.frame(0, (172, 6))
        state.capture(np.empty(0))
        state.frame(0.01, (172, 6))
        self.assertEqual(state.window.size, 2048)
        state.frame(0.16, (172, 6))
        self.assertEqual(state.window.size, 0)
        for index in range(1, 81):
            state.capture(np.empty(0))
            state.frame(0.16 + index * 0.25, (172, 6))
        self.assertEqual(state.amount, 0)
        self.assertFalse(np.any(state.peaks))
        state.capture(np.full(441, 0.03))
        np.testing.assert_array_equal(state.window, np.full(441, 0.03))
        self.assertIn('SYSTEM AUDIO', state.frame(21, (172, 6)))

    def test_empty_idle_stays_settled_without_fft_or_output(self):
        _, _, _, state = exercise([np.ones(2048) * 0.1] * 30 + [np.empty(0)] * 1000)
        with count_calls() as counts:
            for index in range(1000):
                state.capture(np.empty(0))
                self.assertIsNone(state.frame(20 + index * 0.01, (100, 8)))
        self.assertEqual(counts, dict.fromkeys(counts, 0))
        self.assertEqual(state.window.size, 0)

    def test_delayed_capture_after_gap_discards_expired_history(self):
        state = spectrum.SpectrumState()
        state.capture(np.ones(2048) * 0.1, now=0)
        state.frame(0, (172, 6))
        state.capture(np.empty(0), now=0.01)
        state.frame(0.01, (172, 6))
        state.capture(np.full(441, 0.03), now=0.21)
        np.testing.assert_array_equal(state.window, np.full(441, 0.03))

    def test_gap_age_starts_at_capture_not_delayed_draw(self):
        state = spectrum.SpectrumState()
        state.capture(np.ones(2048) * 0.1, now=0)
        state.frame(0, (172, 6))
        state.capture(np.empty(0), now=0.01)
        state.frame(0.11, (172, 6))
        state.capture(np.full(441, 0.03), now=0.18)
        np.testing.assert_array_equal(state.window, np.full(441, 0.03))

    def test_resize_during_short_gap_only_redraws_cached_heights(self):
        state = spectrum.SpectrumState()
        state.capture(np.sin(np.arange(2048) * 0.1) * 0.1)
        state.frame(0, (172, 12))
        previous = state.levels.copy()
        state.capture(np.empty(0))
        with count_calls() as counts:
            frame = state.frame(0.01, (172, 6))
        self.assertIn('\x1b[2J', frame)
        self.assertEqual(counts['rfft'], 0)
        self.assertEqual(counts['render_frame'], 1)
        bars = spectrum.geometry(172, 6)[2]
        expected = previous[:bars] * 5 / 11 * np.exp(-0.01 * 5)
        expected[expected < 0.025] = 0
        np.testing.assert_allclose(state.levels[:bars], expected)

    def test_resize_scales_heights_and_clears_hidden_bands(self):
        state = spectrum.SpectrumState()
        state.frame(0, (172, 12))
        state.levels[:] = 8.8
        state.peaks[:] = 9.9
        frame = state.frame(0, (172, 6))
        _, _, bars, rows = spectrum.geometry(172, 6)
        np.testing.assert_allclose(state.levels[:bars], 4.0)
        np.testing.assert_allclose(state.peaks[:bars], 4.5)
        self.assertTrue(np.all(state.levels <= rows))
        self.assertTrue(np.all(state.peaks <= rows))
        self.assertFalse(np.any(state.levels[bars:]))
        self.assertFalse(np.any(state.peaks[bars:]))
        self.assertIn('\x1b[2J', frame)
        state.frame(0, (12, 0))
        self.assertFalse(np.any(state.levels))
        self.assertFalse(np.any(state.peaks))


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

        def capture(samples, **kwargs):
            result = original_capture(samples, **kwargs)
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


# Frozen from e498739897881d4a117810020de0233a2b9f7beb frame, before fixed-data reuse.
# Keep this oracle independent of the cache; changes require an algorithm contract review.
def original_frame(self, now, size):
    energy = float(np.sqrt(np.mean(self.window ** 2))) if self.window.size else 0.0
    active = energy > 0.0001
    resized = size != self.size
    moving = self.amount > 0 or np.any(self.peaks)
    if not resized and (not active and not moving):
        return None
    if not resized and now - self.last_render < (0.05 if active else 0.25) - 1e-9:
        return None
    elapsed = min(1.0, now - self.last_step) if self.last_step is not None else 0.05
    self.last_step = self.last_render = now
    self.size = size
    _, _, bars, rows = spectrum.geometry(*size)
    self.levels *= np.exp(-elapsed * 5)
    self.peaks = np.maximum(self.levels, self.peaks - elapsed * 2.8)
    self.amount *= np.exp(-elapsed * 2.5)
    if active and bars and rows and self.window.size >= 2:
        values_spectrum = np.abs(np.fft.rfft(self.window * np.hanning(len(self.window)))) / len(self.window)
        edges = np.geomspace(45, 16000, bars + 1)
        indices = np.clip((edges * len(self.window) / spectrum.RATE).astype(int), 1, len(values_spectrum) - 1)
        values = np.array([values_spectrum[indices[i]:max(indices[i] + 1, indices[i + 1])].max()
                           for i in range(bars)])
        self.reference = max(0.0015, values.max() * 1.6, self.reference * 0.985)
        levels = np.clip((values / self.reference) ** 0.6 * rows, 0, rows)
        self.levels[:bars] = np.maximum(levels, self.levels[:bars])
        self.peaks[:bars] = np.maximum(self.levels[:bars], self.peaks[:bars])
        self.amount = max(self.amount, min(1.0, energy * 12))
    self.levels[self.levels < 0.025] = 0
    self.peaks[self.peaks < 0.025] = 0
    if self.amount < 0.015:
        self.amount = 0
    return spectrum.render_frame(self, *size, now, active, resized)


@contextmanager
def count_calls():
    # Closures retain only scalar counts and original callables, never array arguments.
    counts = dict.fromkeys(('hanning', 'geomspace', 'rfft', 'mean', 'render_frame', 'sin', 'cos'), 0)
    with ExitStack() as stack:
        for owner, name in [(np, 'hanning'), (np, 'geomspace'), (np.fft, 'rfft'),
                            (np, 'mean'), (spectrum, 'render_frame'), (np, 'sin'), (np, 'cos')]:
            original = getattr(owner, name)

            def counted(*args, _original=original, _name=name, **kwargs):
                counts[_name] += 1
                return _original(*args, **kwargs)

            stack.enter_context(patch.object(owner, name, counted))
        yield counts


class FixedDataTests(unittest.TestCase):
    def assert_state(self, actual, expected):
        for name in ('window', 'levels', 'peaks'):
            np.testing.assert_array_equal(getattr(actual, name), getattr(expected, name))
        for name in ('reference', 'amount', 'last_render', 'last_step', 'size'):
            self.assertEqual(getattr(actual, name), getattr(expected, name), name)
        self.assertIsNot(actual.window, expected.window)
        self.assertIsNot(actual.levels, expected.levels)
        self.assertIsNot(actual.peaks, expected.peaks)

    def compare_frame(self, actual, expected, now, size):
        result = actual.frame(now, size)
        self.assertEqual(result, original_frame(expected, now, size))
        self.assert_state(actual, expected)
        return result

    def test_frame_oracle_continuous_capture_and_gates(self):
        # Resize and missing packets now have their own corrected contracts.
        for size in [(60, 5), (120, 8), (237, 8), (1, 1), (12, 4)]:
            actual, expected = spectrum.SpectrumState(), spectrum.SpectrumState()
            for index in range(80):
                length = [1, 2, 3, 127, 128, 2047, 2048, 5000][index % 8]
                samples = np.sin(np.arange(length) * (0.1 + index * 0.01)) * 0.1
                if index % 3 == 0:
                    samples = np.column_stack((samples, samples * 0.5))
                for state in (actual, expected):
                    state.capture(samples)
                self.compare_frame(actual, expected, index * 0.05, size)
                self.compare_frame(actual, expected, index * 0.05 + 0.001, size)

    def test_fixed_200_varying_frames_exact_and_one_construction(self):
        actual, expected = spectrum.SpectrumState(), spectrum.SpectrumState()
        chunks = [np.sin(np.arange(2048) * (0.05 + index * 0.001)) * (0.03 + index % 7 * 0.01)
                  for index in range(200)]
        counts = dict.fromkeys(('hanning', 'geomspace', 'rfft', 'render_frame'), 0)
        rendered = 0
        for index, chunk in enumerate(chunks):
            actual.capture(chunk)
            expected.capture(chunk)
            with count_calls() as frame_counts:
                frame = actual.frame(index * 0.05, (120, 8))
            rendered += frame is not None
            for name in counts:
                counts[name] += frame_counts[name]
            self.assertEqual(frame, original_frame(expected, index * 0.05, (120, 8)))
            self.assert_state(actual, expected)
        self.assertEqual(rendered, 200)
        self.assertEqual(counts,
                         {'hanning': 1, 'geomspace': 1, 'rfft': 200, 'render_frame': 200})
        np.testing.assert_array_equal(actual._hann, np.hanning(2048))
        print('FIXED frames=200 rfft=200 hanning=1 geomspace=1; raw ANSI/state exact')

    def test_lengths_stereo_bounded_and_current_key_replacement(self):
        actual, expected = spectrum.SpectrumState(), spectrum.SpectrumState()
        hann_n, band_key = None, None
        for index, length in enumerate([0, 1, 2, 2, 3, 127, 128, 128, 2047, 2048, 2048, 2, 127, 4096]):
            mono = np.linspace(0.02, 0.1, length)
            samples = np.column_stack((mono, mono * 0.5)) if index % 2 else mono
            for state in (actual, expected):
                # Isolate FFT lengths; an empty device packet no longer resets history.
                state.window = np.empty(0)
                state.capture(np.empty(0))
                state.capture(samples)
            n = min(length, 2048)
            bars = spectrum.geometry(120, 8)[2]
            eligible = n >= 2
            old_hann = getattr(actual, '_hann', None)
            old_indices = getattr(actual, '_band_indices', None)
            with count_calls() as counts:
                result = actual.frame(index * 0.05, (120, 8))
            self.assertEqual(result, original_frame(expected, index * 0.05, (120, 8)))
            self.assert_state(actual, expected)
            self.assertEqual(counts['hanning'], int(eligible and hann_n != n))
            self.assertEqual(counts['geomspace'], int(eligible and band_key != (n, bars)))
            self.assertEqual(counts['rfft'], int(eligible))
            if eligible:
                if hann_n == n:
                    self.assertIs(actual._hann, old_hann)
                if band_key == (n, bars):
                    self.assertIs(actual._band_indices, old_indices)
                hann_n, band_key = n, (n, bars)
                np.testing.assert_array_equal(actual._hann, np.hanning(n))
                edges = np.geomspace(45, 16000, bars + 1)
                np.testing.assert_array_equal(actual._band_indices, np.clip(
                    (edges * n / spectrum.RATE).astype(int), 1, n // 2))
        self.assertLessEqual(actual.window.size, 2048)

    def test_resize_with_same_bars_height_and_tiny_geometry(self):
        actual, expected = spectrum.SpectrumState(), spectrum.SpectrumState()
        for state in (actual, expected):
            state.capture(np.ones(2048) * 0.1)
        key = None
        for index, size in enumerate([(120, 8), (120, 9), (121, 9), (60, 5), (237, 8),
                                     (1, 1), (12, 0), (12, 4), (120, 8)]):
            bars, rows = spectrum.geometry(*size)[2:]
            eligible = bool(bars and rows)
            with count_calls() as counts:
                result = actual.frame(index * 0.001, size)
            self.assertTrue(np.all(actual.levels <= rows))
            self.assertTrue(np.all(actual.peaks <= rows))
            self.assertFalse(np.any(actual.levels[bars:]))
            self.assertFalse(np.any(actual.peaks[bars:]))
            lines = [ANSI.sub('', line) for line in re.split(r'\x1b\[\d+;1H', result)[1:]]
            self.assertLessEqual(len(lines), size[1])
            self.assertTrue(all(len(line) <= size[0] - 1 for line in lines))
            self.assertIn('\x1b[2J', result)
            self.assertEqual(counts['hanning'], int(index == 0))
            self.assertEqual(counts['geomspace'], int(eligible and key != (2048, bars)))
            self.assertEqual(counts['rfft'], int(eligible))
            if eligible:
                key = (2048, bars)
        self.assertEqual(spectrum.geometry(120, 9)[2], spectrum.geometry(121, 9)[2])

    def test_real_silence_decay_idle_and_wakeup_exact(self):
        # Empty-packet expiration is checked independently in ContinuityTests/main.
        for empty in (False,):
            with self.subTest(empty=empty):
                actual, expected = spectrum.SpectrumState(), spectrum.SpectrumState()
                for state in (actual, expected):
                    state.capture(np.ones(2048) * 0.1)
                self.compare_frame(actual, expected, 0, (120, 8))
                with count_calls() as counts:
                    self.assertIsNone(actual.frame(0.01, (120, 8)))
                self.assertEqual(counts['rfft'], 0)
                self.assertIsNone(original_frame(expected, 0.01, (120, 8)))
                self.assert_state(actual, expected)
                for state in (actual, expected):
                    state.capture(np.empty(0) if empty else np.zeros(2048))
                for index in range(1, 121):
                    with count_calls() as counts:
                        result = actual.frame(index * 0.05, (120, 8))
                    self.assertEqual(result, original_frame(expected, index * 0.05, (120, 8)))
                    self.assert_state(actual, expected)
                    self.assertEqual((counts['hanning'], counts['geomspace'], counts['rfft']), (0, 0, 0))
                self.assertEqual(actual.amount, 0)
                self.assertFalse(np.any(actual.peaks))
                self.compare_frame(actual, expected, 6.01, (60, 5))
                self.compare_frame(actual, expected, 6.02, (120, 8))
                with count_calls() as counts:
                    for index in range(1000):
                        self.assertIsNone(actual.frame(7 + index * 0.01, (120, 8)))
                self.assertEqual(counts, {'hanning': 0, 'geomspace': 0, 'rfft': 0,
                                         'mean': 0 if empty else 1000, 'render_frame': 0, 'sin': 0, 'cos': 0})
                for index in range(1000):
                    self.assertIsNone(original_frame(expected, 7 + index * 0.01, (120, 8)))
                self.assert_state(actual, expected)
                for state in (actual, expected):
                    state.capture(np.ones(2048) * 0.08)
                with count_calls() as counts:
                    result = actual.frame(18, (120, 8))
                self.assertEqual((counts['hanning'], counts['geomspace'], counts['rfft']), (0, 0, 1))
                self.assertEqual(result, original_frame(expected, 18, (120, 8)))
                self.assert_state(actual, expected)


if __name__ == '__main__':
    unittest.main()
