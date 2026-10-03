"""Windows loopback spectrum with a small, energy-driven depth orbit."""

import logging
import os
import signal
import sys
import time
import warnings
from contextlib import ExitStack
from logging.handlers import RotatingFileHandler
from pathlib import Path

sys.path.insert(0, str(Path(r'D:\terminal-workbench\apps\spectrum-venv\Lib\site-packages')))
import numpy as np

RATE, FRAMES = 44100, 2048
PALETTE = [(139, 213, 202), (138, 173, 244), (198, 160, 246), (245, 189, 230)]
BLOCKS = ' ▁▂▃▄▅▆▇█'
running = True


def stop(_signum, _frame):
    global running
    running = False


def geometry(width, height):
    columns = max(0, width - 1)
    orbit = min(24, columns // 5) if width >= 60 and height >= 5 else 0
    rows = max(0, height - (1 if height >= 3 else 0))
    return columns, orbit, min(80, (columns - orbit + 1) // 2), rows


def color(position, brightness=1):
    position = min(1, max(0, position)) * (len(PALETTE) - 1)
    index = min(len(PALETTE) - 2, int(position))
    fraction = position - index
    rgb = [int((a + (b - a) * fraction) * brightness)
           for a, b in zip(PALETTE[index], PALETTE[index + 1])]
    return f'\x1b[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m'


class SpectrumState:
    def __init__(self):
        self.window = np.empty(0)
        self.levels = np.zeros(80)
        self.peaks = np.zeros(80)
        self.reference = 0.025
        self.amount = 0.0
        self.last_render = float('-inf')
        self.last_step = None
        self.size = None

    def capture(self, samples):
        samples = np.asarray(samples)
        if not samples.size:
            self.window = np.empty(0)
            return False
        mono = samples.mean(axis=1) if samples.ndim == 2 else samples
        self.window = np.concatenate((self.window, mono[-FRAMES:]))[-FRAMES:]
        return True

    def frame(self, now, size):
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
        _, _, bars, rows = geometry(*size)
        self.levels *= np.exp(-elapsed * 5)
        self.peaks = np.maximum(self.levels, self.peaks - elapsed * 2.8)
        self.amount *= np.exp(-elapsed * 2.5)
        if active and bars and rows and self.window.size >= 2:
            spectrum = np.abs(np.fft.rfft(self.window * np.hanning(len(self.window)))) / len(self.window)
            edges = np.geomspace(45, 16000, bars + 1)
            indices = np.clip((edges * len(self.window) / RATE).astype(int), 1, len(spectrum) - 1)
            values = np.array([spectrum[indices[i]:max(indices[i] + 1, indices[i + 1])].max()
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
        return render_frame(self, *size, now, active, resized)


def render_frame(state, width, height, now=0, active=False, clear=False):
    columns, orbit, bars, rows = geometry(width, height)
    status = 1 if height >= 3 else 0
    canvas = [[(' ', '') for _ in range(columns)] for _ in range(rows)]
    for index in range(bars):
        x = index * 2
        for y in range(rows):
            value = min(1, max(0, state.levels[index] - (rows - y - 1)))
            char = BLOCKS[int(value * 8)]
            peak_y = rows - 1 - int(min(rows - 1, state.peaks[index]))
            if char == ' ' and state.peaks[index] and y == peak_y:
                char = '▔'
            canvas[y][x] = (char, color(index / max(1, bars - 1), 0.65 + y / max(1, rows) * 0.35))
    if orbit and state.amount:
        origin = columns - orbit
        for index in range(48):
            angle = index * 2 * np.pi / 48 + now * 0.9
            depth = np.sin(angle)
            scale = (0.55 + 0.45 * state.amount) * (0.8 + depth * 0.18)
            x = int((orbit - 1) / 2 + np.cos(angle) * (orbit - 1) / 2 * scale)
            y = int((rows - 1) / 2 + np.sin(angle + 0.6) * (rows - 1) / 2 * scale)
            brightness = state.amount * (0.5 + (depth + 1) * 0.25)
            canvas[y][origin + x] = ('·' if depth < 0 else ('•' if depth < 0.65 else '●'),
                                     color((index / 48 + now * 0.035) % 1, brightness))
    lines = []
    if status:
        lines.append(('SYSTEM AUDIO' if active else 'AUDIO IDLE')[:columns])
    for line in canvas:
        output, previous_tint = [], ''
        for char, tint in line:
            if char != ' ' and tint != previous_tint:
                output.append(tint)
                previous_tint = tint
            output.append(char)
        lines.append(''.join(output) + '\x1b[0m')
    return ('\x1b[2J' if clear else '') + ''.join(
        f'\x1b[{row + 1};1H{line}\x1b[K' for row, line in enumerate(lines))


def main(recorder=None, *, clock=time.monotonic, size=os.get_terminal_size,
         output=None, should_run=None, sleep=time.sleep):
    output = output or sys.stdout
    should_run = should_run or (lambda: running)
    state = SpectrumState()
    with ExitStack() as stack:
        if recorder is None:
            import soundcard as sc
            speaker = sc.default_speaker()
            loopback = sc.get_microphone(id=speaker.id, include_loopback=True) if speaker else None
            if loopback is None:
                output.write('Audio unavailable'[:max(0, size()[0] - 1)])
                return 1
            recorder = stack.enter_context(loopback.recorder(samplerate=RATE, blocksize=FRAMES))
            signal.signal(signal.SIGINT, stop)
            signal.signal(signal.SIGTERM, stop)
        output.write('\x1b[?1049h\x1b[?25l')
        output.flush()
        # Only the known SoundCard discontinuity warning is diverted, with bounded storage.
        with warnings.catch_warnings():
            original_warning = warnings.showwarning
            logger = logging.getLogger('workbench.spectrum')
            propagate = logger.propagate
            logger.propagate = False
            handler = None

            def showwarning(message, category, filename, lineno, file=None, line=None):
                nonlocal handler
                if str(message) == 'data discontinuity in recording' and category.__name__ == 'SoundcardRuntimeWarning':
                    if handler is None:
                        handler = RotatingFileHandler(Path(__file__).with_suffix('.warnings.log'),
                                                      maxBytes=16384, backupCount=1)
                        logger.addHandler(handler)
                    logger.warning('%s', message)
                else:
                    original_warning(message, category, filename, lineno, file, line)

            warnings.showwarning = showwarning
            try:
                while should_run():
                    if not state.capture(recorder.record(numframes=None)):
                        sleep(0.005)
                    frame = state.frame(clock(), size())
                    if frame is not None:
                        output.write(frame)
                        output.flush()
            finally:
                logger.propagate = propagate
                if handler is not None:
                    logger.removeHandler(handler)
                    handler.close()
                output.write('\x1b[0m\x1b[?25h\x1b[?1049l')
                output.flush()
    return 0


def demo(width=100, height=8):
    state = SpectrumState()
    samples = np.sin(np.arange(FRAMES) * 2 * np.pi * 440 / RATE) * 0.07
    state.capture(samples)
    return state.frame(1.0, (width, height))


if __name__ == '__main__':
    if sys.argv[1:] == ['--demo']:
        sys.stdout.write(demo())
    else:
        raise SystemExit(main())
