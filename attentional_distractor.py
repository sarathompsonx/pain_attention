import csv
import numpy as np
from psychtoolbox import audio
import math
import random
from datetime import datetime
from pathlib import Path
from psychopy import core, event, visual

PARTICIPANT_ID = 'TEST01'
FULL_SCREEN = True
WINDOW_SIZE = (1920, 1080)  # fallback; fullscreen uses the display resolution
BLOCKS = 4
TRIALS_PER_BLOCK = 30
PRACTICE_TRIALS = 30  # target-only; excluded from four experimental blocks
PREVIEW_SECONDS = 0.300
HOME_HOLD_SECONDS = 0.100
SQUARE_SIZE_PX = 130  # temporary, NOT verified Welsh dimensions
HOME_RADIUS_PX = 55
HOME_TOUCH_TOLERANCE_PX = 105  # invisible activation radius, visible home stays 55 px
REACTION_TIMEOUT = 0.500  # beep to HOME release
MOVEMENT_TIMEOUT = 0.500  # HOME release to first touchdown
TIMEOUT_MESSAGE_SECONDS = 1.2
SAVE_DIAGNOSTICS = False  # turn on temporarily if touch troubleshooting is needed
SEED = None

rng = random.Random(SEED)

# Across all four blocks, each ordered target-distractor pair occurs six times.
def make_blocks():
    names = ('left', 'centre', 'right')
    blocks = []
    for b in range(BLOCKS):
        trials = []
        for target_name in names:
            trials.extend({'target': target_name, 'distractor': None} for _ in range(7))
            other = [x for x in names if x != target_name]
            counts = (2, 1) if b % 2 == 0 else (1, 2)
            for distractor_name, count in zip(other, counts):
                trials.extend({'target': target_name, 'distractor': distractor_name} for _ in range(count))
        rng.shuffle(trials)
        assert len(trials) == 30
        blocks.append(trials)
    return blocks


def make_practice_trials():
    """30 target-only practice trials, balanced across all three locations."""
    trials = [{'target': name, 'distractor': None}
              for name in ('left', 'centre', 'right')
              for _ in range(PRACTICE_TRIALS // 3)]
    rng.shuffle(trials)
    return trials

win = visual.Window(size=WINDOW_SIZE, fullscr=FULL_SCREEN, units='pix',
                    color=(-1, -1, -1), colorSpace='rgb', allowGUI=not FULL_SCREEN)
mouse = event.Mouse(win=win, visible=True)
# Confirmed audible on this testing computer: Dell P2418HT / WASAPI device 4.
# PTB device indices can change if audio hardware or Windows settings change.
AUDIO_DEVICE_INDEX = 4
AUDIO_SAMPLE_RATE = 48000
BEEP_FREQUENCY_HZ = 800
BEEP_DURATION_SECONDS = 0.080
BEEP_AMPLITUDE = 0.30  # start conservatively; adjust after listening

beep_stream = audio.Stream(device_id=AUDIO_DEVICE_INDEX, mode=1,
                          freq=AUDIO_SAMPLE_RATE, channels=2)
tone_t = np.arange(round(AUDIO_SAMPLE_RATE * BEEP_DURATION_SECONDS)) / AUDIO_SAMPLE_RATE
beep_samples = (BEEP_AMPLITUDE * np.sin(2 * np.pi * BEEP_FREQUENCY_HZ * tone_t)).astype(np.float32)
# PTB FillBuffer expects [samples, channels], as confirmed in the Dell test.
beep_stereo = np.column_stack((beep_samples, beep_samples))
beep_stream.fill_buffer(beep_stereo)


def play_go_beep():
    """Request playback and return software timestamp (NOT measured acoustic onset)."""
    beep_stream.stop()
    beep_stream.start()
    return core.getTime()
w, h = [float(x) for x in win.size]
home_pos = (0.0, -0.38 * h)
target_y = 0.19 * h
side_x = (target_y - home_pos[1]) * math.tan(math.radians(30))
locations = {'left': (-side_x, target_y), 'centre': (0.0, target_y),
             'right': (side_x, target_y)}

# RGB colors in PsychoPy's -1..1 space. Green is intentionally bright/neon.
WHITE = (1, 1, 1)
RED = (1, -1, -1)
NEON_GREEN = (-1, 1, -1)
BLUE = (-0.6, -0.2, 1)

frames = {name: visual.Rect(win, width=SQUARE_SIZE_PX, height=SQUARE_SIZE_PX,
                            pos=pos, fillColor=None, lineColor=WHITE,
                            lineColorSpace='rgb', lineWidth=5)
          for name, pos in locations.items()}
red_fill = visual.Rect(win, width=SQUARE_SIZE_PX - 10, height=SQUARE_SIZE_PX - 10,
                       fillColor=RED, colorSpace='rgb', lineColor=RED)
green_fill = visual.Rect(win, width=SQUARE_SIZE_PX - 10, height=SQUARE_SIZE_PX - 10,
                         fillColor=NEON_GREEN, colorSpace='rgb', lineColor=NEON_GREEN)
home = visual.Circle(win, radius=HOME_RADIUS_PX, pos=home_pos,
                     fillColor=BLUE, lineColor=WHITE, colorSpace='rgb', lineWidth=3)
message = visual.TextStim(win, color=WHITE, colorSpace='rgb', height=22, wrapWidth=w-100)
heading = visual.TextStim(win, color=WHITE, colorSpace='rgb', height=54,
                          pos=(0, 0.24*h), bold=True, wrapWidth=w-100)
body_text = visual.TextStim(win, color=(0.75, 0.75, 0.75), colorSpace='rgb',
                            height=34, pos=(0, -0.015*h), wrapWidth=w-130)
footer_text = visual.TextStim(win, color=WHITE, colorSpace='rgb',
                              height=27, pos=(0, -0.34*h), wrapWidth=w-100)


fixation = visual.TextStim(win, text='+', pos=locations['centre'], height=48,
                           color=WHITE, colorSpace='rgb')
timeout_text = visual.TextStim(win, text='TIME OUT', pos=(0, 0), height=58,
                               bold=True, color=WHITE, colorSpace='rgb')

# Listen for pyglet pointer events as well as PsychoPy's Mouse polling.
# Some Windows touch drivers deliver contact/release differently.
pointer_events = []
contact_events = []
decision_events = []
def decision(phase, kind, t, pos, button, result):
    decision_events.append((phase, kind, round(t, 6), round(pos[0], 2), round(pos[1], 2), button, result))
try:
    handle = win.winHandle
    def on_mouse_press(x, y, button, modifiers):
        t = core.getTime()
        pointer_events.append(('press', t, int(x), int(y), int(button)))
        contact_events.append(('press', t, (float(x)-w/2, float(y)-h/2), int(button)))
    def on_mouse_release(x, y, button, modifiers):
        t = core.getTime()
        pointer_events.append(('release', t, int(x), int(y), int(button)))
        contact_events.append(('release', t, (float(x)-w/2, float(y)-h/2), int(button)))
    def on_mouse_motion(x, y, dx, dy):
        pointer_events.append(('motion', core.getTime(), int(x), int(y), 0))
    handle.push_handlers(on_mouse_press=on_mouse_press,
                         on_mouse_release=on_mouse_release,
                         on_mouse_motion=on_mouse_motion)
except Exception as exc:
    print('Native pointer event hooks unavailable:', repr(exc), flush=True)


def pointer():
    pos = mouse.getPos()
    buttons = mouse.getPressed()
    return (float(pos[0]), float(pos[1])), tuple(bool(v) for v in buttons)


def at_home(pos):
    return math.hypot(pos[0] - home_pos[0], pos[1] - home_pos[1]) <= HOME_TOUCH_TOLERANCE_PX


def draw(trial=None, note='', show_fixation=False):
    # Fill first; ALWAYS redraw outlines over the colored squares.
    if trial is not None:
        red_fill.pos = locations[trial['target']]
        red_fill.draw()
        if trial['distractor'] is not None:
            green_fill.pos = locations[trial['distractor']]
            green_fill.draw()
    for outline in frames.values():
        outline.draw()
    home.draw()
    if show_fixation:
        fixation.draw()
    if note:
        message.text = note
        message.pos = (0, -0.08*h)
        message.draw()
    win.flip()


def instruction_screen(title, body, footer='Press SPACE to continue'):
    """Wait indefinitely for the researcher/participant to advance."""
    event.clearEvents()
    # Remove queued touches from the prior trial while the instructions are shown.
    contact_events.clear()
    while True:
        keys = event.getKeys(keyList=['space', 'escape'])
        if 'escape' in keys:
            return False
        if 'space' in keys:
            contact_events.clear()
            return True
        heading.text = title
        body_text.text = body
        footer_text.text = footer
        heading.draw()
        body_text.draw()
        footer_text.draw()
        win.flip()


def show_timeout():
    start = core.getTime()
    while core.getTime() - start < TIMEOUT_MESSAGE_SECONDS:
        if 'escape' in event.getKeys(['escape']):
            return False
        timeout_text.draw()
        win.flip()
    return True


def trial_row(b, n, trial, mode, status, go=None, released=None, contact=None, endpoint=None):
    target_pos = locations[trial['target']]
    err = math.hypot(endpoint[0]-target_pos[0], endpoint[1]-target_pos[1]) if endpoint else None
    return {'participant': PARTICIPANT_ID, 'block': b, 'trial': n,
            'input_mode': mode, 'target': trial['target'],
            'distractor': trial['distractor'] or 'none',
            'distractor_present': int(trial['distractor'] is not None),
            'reaction_time_s': round(released-go, 5) if released is not None and go is not None else '',
            'movement_time_s': round(contact-released, 5) if contact is not None and released is not None else '',
            'go_to_contact_s': round(contact-go, 5) if contact is not None and go is not None else '',
            'target_centre_x_px': round(target_pos[0], 2),
            'target_centre_y_px': round(target_pos[1], 2),
            'touch_x_px': round(endpoint[0], 2) if endpoint else '',
            'touch_y_px': round(endpoint[1], 2) if endpoint else '',
            'endpoint_x_px': round(endpoint[0], 2) if endpoint else '',
            'endpoint_y_px': round(endpoint[1], 2) if endpoint else '',
            'endpoint_error_px': round(err, 2) if err is not None else '',
            'hit': int(abs(endpoint[0]-target_pos[0]) <= SQUARE_SIZE_PX/2 and
                       abs(endpoint[1]-target_pos[1]) <= SQUARE_SIZE_PX/2) if endpoint else 0,
            'status': status}


def run_trial(trial, b, n, mode):
    # Native touch: Windows touchscreen often reports button 4 (right click),
    # whereas a physical mouse reports button 1. We accept either for diagnosis.
    # State is driven by native events, not by mouse.getPressed().
    if mode == 'touch':
        # Pyglet window coordinates: bottom-left origin; PsychoPy pix: centre origin.
        # Touch driver may send home as button 4, target as button 1, with a
        # press/release pair in <1 ms. We use the event timestamp of the PRESS.
        contact_events.clear()
        phase = 'home'
        down = False
        home_press_time = None
        preview_start = None
        go = None
        released = None
        phase_start = core.getTime()
        while True:
            if 'escape' in event.getKeys(['escape']):
                return None
            # Read and clear the event queue once per frame. Events are handled
            # in their original order, including multiple events per frame.
            pending = contact_events[:]
            contact_events.clear()
            for kind, t, pos, button in pending:
                if button not in (1, 4):
                    decision(phase, kind, t, pos, button, 'ignored_button')
                    continue
                if phase == 'home':
                    if kind == 'press' and at_home(pos):
                        down = True
                        home_press_time = t
                        decision(phase, kind, t, pos, button, 'home_press_accepted')
                    elif kind == 'release' and down:
                        down = False
                        home_press_time = None
                        decision(phase, kind, t, pos, button, 'home_release_before_hold')
                    else:
                        decision(phase, kind, t, pos, button, 'ignored_outside_home_or_unmatched')
                elif phase == 'preview':
                    if kind == 'release' and down:
                        decision(phase, kind, t, pos, button, 'early_release')
                        return trial_row(b, n, trial, mode, 'early_release')
                    decision(phase, kind, t, pos, button, 'preview_no_change')
                elif phase == 'go':
                    if released is None:
                        if kind == 'release' and t-go < REACTION_TIMEOUT:
                            released = t
                            decision(phase, kind, t, pos, button, 'home_release_rt')
                        else:
                            decision(phase, kind, t, pos, button, 'waiting_home_release')
                    elif kind == 'press' and t-released < MOVEMENT_TIMEOUT:
                        if at_home(pos):
                            decision(phase, kind, t, pos, button, 'ignored_press_in_home_zone')
                        else:
                            # Record EVERY contact outside home, even if off-target.
                            # Accuracy/hit is evaluated separately in trial_row.
                            decision(phase, kind, t, pos, button, 'endpoint_recorded')
                            return trial_row(b, n, trial, mode, 'touch_endpoint',
                                             go, released, t, pos)
                    else:
                        decision(phase, kind, t, pos, button, 'ignored_release_waiting_target')
            now = core.getTime()
            if phase == 'home':
                if down and home_press_time is not None and now-home_press_time >= HOME_HOLD_SECONDS:
                    phase = 'preview'
                    preview_start = now
                    decision('home', 'state', now, home_pos, 0, 'hold_completed')
                else:
                    draw(show_fixation=True)
            elif phase == 'preview':
                if now-preview_start >= PREVIEW_SECONDS:
                    # Flip the stimulus frame, then play tone; approximate go timestamp.
                    draw(trial)
                    go = play_go_beep()
                    phase = 'go'
                    decision('preview', 'state', go, home_pos, 0, 'go_signal')
                else:
                    draw(trial)
            else:
                if released is None and now-go >= REACTION_TIMEOUT:
                    show_timeout()
                    return trial_row(b, n, trial, mode, 'timeout_no_release', go, released)
                if released is not None and now-released >= MOVEMENT_TIMEOUT:
                    show_timeout()
                    return trial_row(b, n, trial, mode, 'timeout_no_target_press', go, released)
                draw(trial)

    # Mouse-hold mode remains unchanged for comparison.
    while any(pointer()[1]):
        if 'escape' in event.getKeys(['escape']): return None
        draw(note='Release to begin the next trial.')
    hold_since = None
    while True:
        if 'escape' in event.getKeys(['escape']): return None
        pos, buttons = pointer()
        if buttons[0] and at_home(pos):
            if hold_since is None: hold_since = core.getTime()
            if core.getTime()-hold_since >= HOME_HOLD_SECONDS: break
        else:
            hold_since = None
        draw(show_fixation=True)
    start = core.getTime()
    while core.getTime()-start < PREVIEW_SECONDS:
        if 'escape' in event.getKeys(['escape']): return None
        pos, buttons = pointer()
        if not buttons[0] or not at_home(pos):
            return trial_row(b, n, trial, mode, 'early_release')
        draw(trial)
    go = play_go_beep()
    previous_down = pointer()[1][0]
    released = None
    while core.getTime()-go < REACTION_TIMEOUT + MOVEMENT_TIMEOUT:
        if 'escape' in event.getKeys(['escape']): return None
        pos, buttons = pointer()
        down = buttons[0]
        now = core.getTime()
        if released is None and now-go >= REACTION_TIMEOUT:
            show_timeout()
            return trial_row(b, n, trial, mode, 'timeout_no_release', go)
        if released is not None and now-released >= MOVEMENT_TIMEOUT:
            show_timeout()
            return trial_row(b, n, trial, mode, 'timeout_no_target_press', go, released)
        if released is None and previous_down and not down:
            released = now
        elif released is not None and not previous_down and down:
            return trial_row(b, n, trial, mode, 'response', go, released, now, pos)
        previous_down = down
        draw(trial)
    show_timeout()
    return trial_row(b, n, trial, mode, 'timeout', go, released)


out_dir = Path(__file__).resolve().parent / 'data'
out_dir.mkdir(exist_ok=True)
stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
out_file = out_dir / f'{PARTICIPANT_ID}_{stamp}.csv'
events_file = out_dir / f'{PARTICIPANT_ID}_{stamp}_pointer_events.csv'
decisions_file = out_dir / f'{PARTICIPANT_ID}_{stamp}_touch_decisions.csv'
fields = ['participant', 'block', 'trial', 'input_mode', 'target', 'distractor',
          'distractor_present', 'reaction_time_s', 'movement_time_s',
          'go_to_contact_s', 'target_centre_x_px', 'target_centre_y_px',
          'touch_x_px', 'touch_y_px', 'endpoint_x_px', 'endpoint_y_px',
          'endpoint_error_px', 'hit', 'status']

try:
    # Participant-facing version defaults to the validated native touchscreen path.
    # Keep the mouse-mode implementation available in run_trial for later debugging.
    mode = 'touch'
    with out_file.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        # A single initial instruction screen leads straight into practice.
        proceed = instruction_screen(
            'Practice',
            'Place your finger on the blue HOME position and wait for the beep.\n\n'
            'Then reach toward the RED square. Ignore all other colors.',
            'Press SPACE to start 30 practice trials.')
        stopped = not proceed
        if proceed:
            # Practice is block 0 in the CSV; experimental blocks remain 1–4.
            for n, trial in enumerate(make_practice_trials(), 1):
                row = run_trial(trial, 0, n, mode)
                if row is None:
                    stopped = True
                    break
                writer.writerow(row)
                fh.flush()
                start = core.getTime()
                while core.getTime() - start < 0.35:
                    draw()

        if not stopped:
            # No duplicate instruction page: this is the only transition
            # between practice and the first experimental block.
            proceed = instruction_screen(
                'Practice complete',
                'You have finished the practice trials.\n\n'
                'Please wait for the researcher.',
                'RESEARCHER: Press SPACE to start Block 1.')
            stopped = not proceed

        if not stopped:
            blocks = make_blocks()
            for b, trials in enumerate(blocks, 1):
                for n, trial in enumerate(trials, 1):
                    row = run_trial(trial, b, n, mode)
                    if row is None:
                        stopped = True
                        break
                    writer.writerow(row)
                    fh.flush()
                    start = core.getTime()
                    while core.getTime() - start < 0.35:
                        draw()
                if stopped:
                    break
                if b < len(blocks):
                    proceed = instruction_screen(
                        f'Block {b} complete',
                        'You have finished this block.\n\n'
                        'Please wait for the researcher.',
                        f'RESEARCHER: Press SPACE to start Block {b + 1}.')
                    if not proceed:
                        stopped = True
                        break
            if not stopped:
                instruction_screen(
                    'Task complete',
                    'Thank you for completing the reaching task.\n\n'
                    'Please wait for the researcher.',
                    'Press SPACE to finish.')

finally:
    if SAVE_DIAGNOSTICS:
        with events_file.open('w', newline='', encoding='utf-8') as ef:
            ew = csv.writer(ef)
            ew.writerow(['event_type', 'timestamp_s', 'window_x', 'window_y', 'button'])
            ew.writerows(pointer_events)
        with decisions_file.open('w', newline='', encoding='utf-8') as df:
            dw = csv.writer(df)
            dw.writerow(['phase', 'event_type', 'timestamp_s', 'psychopy_x', 'psychopy_y', 'button', 'decision'])
            dw.writerows(decision_events)
    print('Saved trials:', out_file, flush=True)
    beep_stream.close()
    win.close()
    core.quit()