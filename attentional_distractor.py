import csv
import math
import random
from datetime import datetime
from pathlib import Path
from psychopy import core, event, sound, visual

PARTICIPANT_ID = 'TEST01'
FULL_SCREEN = False
WINDOW_SIZE = (1000, 700)
BLOCKS = 4
TRIALS_PER_BLOCK = 30
PREVIEW_SECONDS = 0.300
HOME_HOLD_SECONDS = 0.100
SQUARE_SIZE_PX = 130  # temporary, NOT verified Welsh dimensions
HOME_RADIUS_PX = 55
HOME_TOUCH_TOLERANCE_PX = 105  # invisible activation radius, visible home stays 55 px
RESPONSE_TIMEOUT = 4.0
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

win = visual.Window(size=WINDOW_SIZE, fullscr=FULL_SCREEN, units='pix',
                    color=(-1, -1, -1), colorSpace='rgb', allowGUI=not FULL_SCREEN)
mouse = event.Mouse(win=win, visible=True)
beep = sound.Sound(value=800, secs=0.08, volume=0.7)
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
message = visual.TextStim(win, color=WHITE, colorSpace='rgb', height=19, wrapWidth=w-30)

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


def draw(trial=None, note=''):
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
    if note:
        message.text = note
        message.pos = (0, -0.08*h)
        message.draw()
    win.flip()


def wait_key(prompt, allowed=('space',)):
    event.clearEvents()
    while True:
        if 'escape' in event.getKeys(['escape']):
            return None
        draw(note=prompt)
        found = event.getKeys(keyList=list(allowed))
        if found:
            return found[0]


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
                        if kind == 'release':
                            released = t
                            decision(phase, kind, t, pos, button, 'home_release_rt')
                        else:
                            decision(phase, kind, t, pos, button, 'waiting_home_release')
                    elif kind == 'press':
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
                    draw(note='TOUCH HOME: hold finger in blue circle\n'
                              'Larger invisible tolerance enabled | finger down: ' + str(down))
            elif phase == 'preview':
                if now-preview_start >= PREVIEW_SECONDS:
                    # Flip the stimulus frame, then play tone; approximate go timestamp.
                    draw(trial)
                    beep.play()
                    go = core.getTime()
                    phase = 'go'
                    decision('preview', 'state', go, home_pos, 0, 'go_signal')
                else:
                    draw(trial)
            else:
                if now-go >= RESPONSE_TIMEOUT:
                    return trial_row(b, n, trial, mode,
                        'timeout_no_release' if released is None else 'timeout_no_target_press',
                        go, released)
                draw(trial, note='GO: lift HOME then touch RED (any landing logged)')

    # Mouse-hold mode remains unchanged for comparison.
    while any(pointer()[1]):
        if 'escape' in event.getKeys(['escape']): return None
        draw(note='Release all buttons before the next trial')
    hold_since = None
    while True:
        if 'escape' in event.getKeys(['escape']): return None
        pos, buttons = pointer()
        if buttons[0] and at_home(pos):
            if hold_since is None: hold_since = core.getTime()
            if core.getTime()-hold_since >= HOME_HOLD_SECONDS: break
        else:
            hold_since = None
        draw(note=f'MOUSE | hold blue home | position {pos[0]:.0f}, {pos[1]:.0f} | buttons {buttons}')
    start = core.getTime()
    while core.getTime()-start < PREVIEW_SECONDS:
        if 'escape' in event.getKeys(['escape']): return None
        pos, buttons = pointer()
        if not buttons[0] or not at_home(pos):
            return trial_row(b, n, trial, mode, 'early_release')
        draw(trial)
    beep.play()
    go = core.getTime()
    previous_down = pointer()[1][0]
    released = None
    while core.getTime()-go < RESPONSE_TIMEOUT:
        if 'escape' in event.getKeys(['escape']): return None
        pos, buttons = pointer()
        down = buttons[0]
        now = core.getTime()
        if released is None and previous_down and not down:
            released = now
        elif released is not None and not previous_down and down:
            return trial_row(b, n, trial, mode, 'response', go, released, now, pos)
        previous_down = down
        draw(trial)
    return trial_row(b, n, trial, mode, 'timeout', go)


out_dir = Path(__file__).resolve().parent / 'data'
out_dir.mkdir(exist_ok=True)
stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
out_file = out_dir / f'{PARTICIPANT_ID}_{stamp}.csv'
events_file = out_dir / f'{PARTICIPANT_ID}_{stamp}_pointer_events.csv'
decisions_file = out_dir / f'{PARTICIPANT_ID}_{stamp}_touch_decisions.csv'
fields = ['participant', 'block', 'trial', 'input_mode', 'target', 'distractor',
          'distractor_present', 'reaction_time_s', 'movement_time_s',
          'go_to_contact_s', 'endpoint_x_px', 'endpoint_y_px',
          'endpoint_error_px', 'hit', 'status']

try:
    mode_key = wait_key('Press M for mouse-hold mode, or T for native TOUCH mode.\n\nESC quits.', ('m', 't'))
    if mode_key is not None:
        mode = 'mouse' if mode_key == 'm' else 'touch'
        with out_file.open('w', newline='', encoding='utf-8') as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            if wait_key('All THREE white square outlines should be visible on the next screen.\n\n'
                        'Mouse or touch: HOLD blue home.\n'
                        'After 300 ms, a beep tells you to GO.\n'
                        'After beep: RELEASE home, then TOUCH target.\n\nPress SPACE to start.'):
                stopped = False
                for b, trials in enumerate(make_blocks(), 1):
                    if wait_key(f'Block {b} / 4. Press SPACE to start.') is None: break
                    for n, trial in enumerate(trials, 1):
                        row = run_trial(trial, b, n, mode)
                        if row is None:
                            stopped = True
                            break
                        writer.writerow(row)
                        fh.flush()
                        start = core.getTime()
                        while core.getTime()-start < 0.35:
                            draw(note=f'{row["status"]} | Trial {n} / 30')
                    if stopped: break
                if not stopped: wait_key('Finished. Press SPACE to exit.')
finally:
    with events_file.open('w', newline='', encoding='utf-8') as ef:
        ew = csv.writer(ef)
        ew.writerow(['event_type', 'timestamp_s', 'window_x', 'window_y', 'button'])
        ew.writerows(pointer_events)
    with decisions_file.open('w', newline='', encoding='utf-8') as df:
        dw = csv.writer(df)
        dw.writerow(['phase', 'event_type', 'timestamp_s', 'psychopy_x', 'psychopy_y', 'button', 'decision'])
        dw.writerows(decision_events)
    print('Saved touch decisions:', decisions_file, flush=True)
    print('Saved trials:', out_file, flush=True)
    print('Saved native pointer events:', events_file, flush=True)
    win.close()
    core.quit()