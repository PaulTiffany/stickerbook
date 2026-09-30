"""Host-owned, interruptible bodies for ongoing child-directed Jev play.

A remote choice selects a finite steering intent, never a coordinate. Each
continuation has at most six ticks. Every tick derives fresh host coordinates
and submits an ordinary kernel command. The child may revoke the activity at
any point; neither a late choice nor a fresh observer lease can restart it.
"""
from collections import deque
from dataclasses import dataclass, field
import math
import json
from threading import Event, Lock, Thread
import time

from stickerbook_core import MOVE_STICKER, ANIMATE_OWN_STICKER, SET_STICKER_FACING
from governed_history import ORIGIN_GESTURE_JEV, ORIGIN_OMEGALLM_JEV
from jev_runtime import JevRuntimeError

MOTOR_TICK_SECONDS = .25
CONTINUATION_TICKS = 6
HEADING_COUNT = 16
SPEEDS = (.035, .055, .08)  # page fractions/second
OBSERVER_LEASE_SECONDS = 4.0
MAX_ACTIVE_SUBJECTS = 8
DECISION_HORIZON = 6


@dataclass(frozen=True)
class Steering:
    heading: int | None = None
    speed: int = 1
    clip: str | None = None
    facing: str | None = None
    stop: bool = False
    relative: str | None = None


@dataclass
class Activity:
    goal: dict
    actor: str
    requested_by: str
    translated_by: str | None
    serial: int
    activation: object
    expected_revision: int
    watermark: int
    heading: int = 0
    speed: int = 1
    remaining: int = 0
    turns: int = 0
    sequence: int = 0
    delta: dict = field(default_factory=lambda: {'dx': 0.0, 'dy': 0.0})
    headings: deque = field(default_factory=lambda: deque(maxlen=6))
    relative: str | None = None
    next_tick: float = 0.0
    next_decision: float = 0.0

    @property
    def subject(self):
        return self.goal['subject']

    def describe(self):
        return {'subject': self.subject, 'goal': dict(self.goal),
                'heading': self.heading, 'headingCount': HEADING_COUNT,
                'speed': SPEEDS[self.speed], 'lastDelta': dict(self.delta),
                'moving': self.remaining > 0, 'remainingTicks': self.remaining,
                'recentTurns': min(self.turns, DECISION_HORIZON),
                'recentSteeringHeadings': list(self.headings),
                'steering': self.relative or 'heading'}


class SerializedJevRuntime:
    """One RPC choice in flight across foreground work and page players."""
    def __init__(self, runtime):
        self.runtime = runtime
        self.gate = Lock()

    def available(self):
        return self.runtime.available()

    def choose(self, **kwargs):
        with self.gate:
            return self.runtime.choose(**kwargs)


class MotionPlayer:
    def __init__(self, controller, *, clock=time.monotonic, threaded=True):
        self.controller = controller
        self.clock = clock
        self.threaded = threaded
        self.activities = {}
        self.audit = deque(maxlen=128)
        self.serial = 0
        self.lease = 0.0
        self.pending = None
        self.worker = None
        self.wake = Event()
        self.closed = False
        self.cursor = 0
        self.child_versions = {}

    def observe(self):
        # Observation renews existing child invitations; it creates none.
        with self.controller._world():
            self.lease = self.clock() + OBSERVER_LEASE_SECONDS

    def describe(self):
        with self.controller._world():
            return [a.describe() for a in self.activities.values()]

    def _note(self, kind, **data):
        self.audit.append({'kind': kind, 'at': round(self.clock(), 6), **data})

    def stop(self, subject=None, reason='child-interrupted'):
        if subject is not None and not isinstance(subject,str):
            return
        with self.controller._world():
            subjects = list(self.activities) if subject is None else [subject]
            for sid in subjects:
                if sid not in self.activities and self.controller.kernel.sticker(sid) is None:
                    continue
                if reason in {'child-interrupted', 'human-superseded', 'child-grabbed', 'child-redirected', 'semantic-work', 'child-left-page'}:
                    self.child_versions[sid] = self.child_versions.get(sid,0) + 1
                a = self.activities.pop(sid, None)
                if a:
                    self._note('stop', subject=sid, serial=a.serial, reason=reason)
        self.wake.set()

    def start(self, raw_goal, *, actor, requested_by, translated_by=None, expected_child_version=None):
        with self.controller._world():
            if self.closed or self.controller.activity() is None:
                return {'ok': False, 'error': 'page-changed'}
            goal, error = self.controller.normalize_goal(raw_goal)
            if error:
                return {'ok': False, 'error': error}
            if expected_child_version is not None and self.child_versions.get(goal['subject'],0) != expected_child_version:
                return {'ok':False,'error':'human-superseded'}
            if goal['subject'] not in self.activities and len(self.activities) >= MAX_ACTIVE_SUBJECTS:
                return {'ok': False, 'error': 'motion-capacity'}
            previous = self.activities.get(goal['subject'])
            if previous and goal['intent'] == 'animate' and 'target' not in goal and 'target' in previous.goal:
                goal['target'] = dict(previous.goal['target'])
            self.stop(goal['subject'], 'child-redirected')
            sticker = self.controller.kernel.sticker(goal['subject'])
            self.serial += 1
            a = Activity(goal, actor, requested_by, translated_by, self.serial,
                         self.controller.activity(), sticker.revision,
                         self.controller._history_watermark())
            if previous:
                a.heading, a.speed, a.delta = previous.heading, previous.speed, dict(previous.delta)
            self.activities[a.subject] = a
            self.lease = self.clock() + OBSERVER_LEASE_SECONDS
            self._note('start', subject=a.subject, serial=a.serial, goal=dict(goal))
            if self.threaded and self.worker is None:
                self.worker = Thread(target=self._run, name='stickerbook-motor', daemon=True)
                self.worker.start()
        self.wake.set()
        return {'ok': True, 'goal': dict(goal), 'activity': a.describe(), 'result': 'playing'}

    def _valid(self, a):
        c = self.controller
        if self.activities.get(a.subject) is not a:
            return False
        if c.activity() != a.activation or a.activation is None:
            self.stop(a.subject, 'page-changed')
            return False
        if self.clock() > self.lease:
            self.stop(a.subject, 'observer-left')
            return False
        sticker = c.kernel.sticker(a.subject)
        if sticker is None:
            self.stop(a.subject, 'subject-removed')
            return False
        if c._human_moved_since(a.subject, a.watermark):
            self.stop(a.subject, 'human-superseded')
            return False
        if sticker.revision != a.expected_revision:
            self.stop(a.subject, 'stale-subject')
            return False
        return True

    @staticmethod
    def _point(sticker, heading, speed):
        angle = heading * math.tau / HEADING_COUNT
        distance = SPEEDS[speed] * MOTOR_TICK_SECONDS
        return (round(sticker.x + math.cos(angle) * distance, 6),
                round(sticker.y + math.sin(angle) * distance, 6))

    def _target_point(self, a):
        target = a.goal.get('target')
        if not target:
            return None
        if target['kind'] == 'point':
            return (target['x'],target['y'])
        sticker = self.controller.kernel.sticker(target['id'])
        return None if sticker is None else (sticker.x,sticker.y)

    def _bearing(self, a):
        sticker = self.controller.kernel.sticker(a.subject)
        point = self._target_point(a)
        if point is None:
            return None
        return round(math.atan2(point[1]-sticker.y,point[0]-sticker.x) * HEADING_COUNT/math.tau) % HEADING_COUNT

    def _relative_heading(self, a, relative):
        bearing = self._bearing(a)
        if bearing is None:
            return a.heading
        return (bearing + {'toward':0, 'tangent-left':-4, 'tangent-right':4}[relative]) % HEADING_COUNT

    def _target_context(self, a):
        sticker = self.controller.kernel.sticker(a.subject)
        target = self._target_point(a)
        if target is None:
            return None
        dx,dy = target[0]-sticker.x,target[1]-sticker.y
        distance = math.hypot(dx,dy)
        previous_distance = math.hypot(dx+a.delta['dx'],dy+a.delta['dy'])
        return {'delta':{'dx':round(dx,6),'dy':round(dy,6)},
                'distance':round(distance,6),'bearing':self._bearing(a),
                'near':distance <= .08,
                'trend':'closer' if distance < previous_distance else 'farther' if distance > previous_distance else 'unchanged'}

    def choices(self, a):
        c = self.controller
        sticker = c.kernel.sticker(a.subject)
        legal = c.kernel.available_actions(a.actor)
        choices = {'NOOP': Steering(stop=True), 'STOP': Steering(stop=True)}
        descriptions = {'NOOP': 'Pause this short episode. No positional mutation; the child invitation remains until interrupted.', 'STOP': 'Stop travelling now. No continuation; the next episode may change pose or steering if the child still invites play.'}
        motions = {'CONTINUE': a.heading, 'LEFT-SMALL': (a.heading - 1) % HEADING_COUNT,
                   'RIGHT-SMALL': (a.heading + 1) % HEADING_COUNT,
                   'LEFT-LARGE': (a.heading - 2) % HEADING_COUNT,
                   'RIGHT-LARGE': (a.heading + 2) % HEADING_COUNT}
        motions.update({name: heading for name, heading in
                        [('E',0),('SE',2),('S',4),('SW',6),('W',8),('NW',10),('N',12),('NE',14)]})
        options = [(name, heading, a.speed, None) for name, heading in motions.items()]
        options += [('SLOW', a.heading, max(0,a.speed-1), a.relative), ('FASTER', a.heading, min(2,a.speed+1), a.relative)]
        target_point = self._target_point(a)
        if target_point is not None:
            options += [(name,self._relative_heading(a,relative),a.speed,relative)
                        for name,relative in [('TOWARD-TARGET','toward'),('AROUND-LEFT','tangent-left'),('AROUND-RIGHT','tangent-right')]]
        clips = [command.param('animation') for command in legal.values()
                 if command.action == ANIMATE_OWN_STICKER and command.object_id == a.subject]
        # A composite offered intent pairs legal pose vocabulary with steering;
        # it becomes separate ordinary animation and movement receipts.
        for name, heading, speed, relative in options:
            point = self._point(sticker, heading, speed)
            if not all(0 <= value <= 1 for value in point):
                continue
            probe = c.kernel.available_actions(a.actor, move_candidates={'BODY': point})
            if 'MOVE:%s:BODY' % a.subject not in probe:
                continue
            for clip in [None, *clips]:
                key = 'MOVE:%s:%s%s' % (a.subject, name, '' if clip is None else '+CLIP-'+clip)
                choices[key] = Steering(heading, speed, clip, relative=relative)
                descriptions[key] = ('Steer %s (heading %d/16); travel at %.3f page fractions/sec '
                    'for at most %d ticks of %.1f seconds%s. Child interruption cancels immediately.'
                    % (name, heading, SPEEDS[speed], CONTINUATION_TICKS, MOTOR_TICK_SECONDS,
                       '' if clip is None else "; also set clip '%s'" % clip))
                if relative:
                    descriptions[key] += (' Travel toward the target.' if relative == 'toward' else ' Curve around the target in a short local arc, keeping roughly the current radius.') + ' Sense the target and derive a finite heading at each of the six ticks.'
                if target_point:
                    distance = math.hypot(point[0]-target_point[0],point[1]-target_point[1])
                    descriptions[key] += ' Distance to current target after first tick: %.4f.' % distance
        for key, command in legal.items():
            if command.object_id != a.subject:
                continue
            if command.action == ANIMATE_OWN_STICKER:
                choices[key] = Steering(clip=command.param('animation'))
                descriptions[key] = "Set clip '%s' without changing steering; existing bounded travel may continue." % command.param('animation')
            elif command.action == SET_STICKER_FACING:
                choices[key] = Steering(facing=command.param('facing'))
                descriptions[key] = 'Face %s; existing bounded travel may continue.' % command.param('facing')
        return choices, descriptions

    def _submit(self, a, key, *, moves=None):
        c = self.controller
        a.sequence += 1
        receipt = c.kernel.propose_key(a.actor, key, 'motor-%d-%d' % (a.serial,a.sequence),
            based_on_revision=c.kernel.revision, requested_by=a.requested_by,
            translated_by=a.translated_by, selected_by=c.selector_id, move_candidates=moves)
        c._record(receipt, origin=ORIGIN_OMEGALLM_JEV if a.translated_by else ORIGIN_GESTURE_JEV,
                  key=None if moves is not None else key, subject_id=a.subject)
        sticker = c.kernel.sticker(a.subject)
        if receipt.accepted and sticker:
            a.expected_revision = sticker.revision
        self._note('receipt', subject=a.subject, serial=a.serial, receipt=receipt.to_dict(),
                   position=None if sticker is None else {'x':sticker.x,'y':sticker.y})
        if not receipt.accepted:
            self.stop(a.subject, receipt.reason)
        return receipt

    def _decision(self, a, choices, kwargs):
        start = self.clock()
        try:
            result = self.controller.runtime.choose(**kwargs)
        except JevRuntimeError as exc:
            result = {'ok':False,'error':exc.code}
        except Exception:
            result = {'ok': False, 'error': 'jev-runtime-error'}
        with self.controller._world():
            # A decision may be late while its finite previous continuation
            # advances. It carries steering, not an old absolute destination.
            if self._valid(a):
                self._note('decision', subject=a.subject, serial=a.serial,
                           seconds=round(self.clock()-start,6), choice=result.get('choice') if isinstance(result,dict) and isinstance(result.get('choice'),str) and result.get('choice') in choices else None)
                choice = result.get('choice') if isinstance(result,dict) and result.get('ok') else None
                if not isinstance(choice,str) or choice not in choices:
                    safe_errors={'jev-busy','jev-not-ready','jev-timeout','jev-request-refused',
                                 'jev-request-too-large','jev-http-error','jev-unavailable','jev-failed-closed'}
                    error=result.get('error') if isinstance(result,dict) else None
                    reason='unknown-jev-choice' if choice is not None else error if isinstance(error,str) and error in safe_errors else 'jev-runtime-error'
                    self.stop(a.subject,reason)
                else:
                    steer = choices[choice]
                    if steer.stop:
                        self._submit(a, 'NOOP')
                        a.remaining = 0
                        a.turns += 1
                        a.next_decision = self.clock() + 1.0
                        self._note('pause',subject=a.subject,serial=a.serial,reason='noop' if choice == 'NOOP' else 'stop')
                    else:
                        if steer.clip is not None:
                            self._submit(a, 'ANIMATE:%s:%s' % (a.subject,steer.clip))
                        if steer.facing is not None:
                            self._submit(a, 'FACE:%s:%s' % (a.subject,steer.facing.upper()))
                        if a.subject in self.activities and steer.heading is not None:
                            a.heading, a.speed, a.relative = steer.heading, steer.speed, steer.relative
                            a.headings.append(a.heading)
                            a.remaining = CONTINUATION_TICKS
                            a.next_tick = max(a.next_tick, self.clock())
                        a.turns += 1
                        # Pure pose choices must not spin an inference loop.
                        a.next_decision = self.clock() + (.4 if steer.heading is None else MOTOR_TICK_SECONDS)
            self.pending = None
        self.wake.set()

    def pump(self):
        c = self.controller
        with c._world():
            for a in list(self.activities.values()):
                if not self._valid(a):
                    continue
                now = self.clock()
                if a.remaining and now >= a.next_tick:
                    sticker = c.kernel.sticker(a.subject)
                    if a.relative:
                        if self._target_point(a) is None:
                            self.stop(a.subject,'target-removed')
                            continue
                        a.heading = self._relative_heading(a,a.relative)
                    point = self._point(sticker,a.heading,a.speed)
                    if not all(0 <= v <= 1 for v in point):
                        a.remaining = 0
                        self._note('boundary',subject=a.subject,serial=a.serial)
                    else:
                        before = (sticker.x,sticker.y)
                        self._submit(a,'MOVE:%s:BODY' % a.subject,moves={'BODY':point})
                        a.delta = {'dx':round(point[0]-before[0],6),'dy':round(point[1]-before[1],6)}
                        a.remaining -= 1
                        a.next_tick = now + MOTOR_TICK_SECONDS
            eligible = [a for a in self.activities.values() if self.clock() >= a.next_decision]
            if self.pending is None and eligible:
                a = eligible[self.cursor % len(eligible)]
                self.cursor += 1
                choices, descriptions = self.choices(a)
                scene = c._scene(a.actor,a.goal,choices)
                # Keys already live in the Decisions criteria; duplicating them
                # in state consumed its independent 4000-character ceiling.
                scene.pop('available_actions',None)
                scene.pop('goal',None)
                scene.pop('pattern',None)
                scene['known_patterns'] = [{**p,'steps':p['steps'][:2],
                    'stepsOmitted':max(0,len(p['steps'])-2)} for p in scene['known_patterns']]
                scene['motion'] = {**a.describe(), 'targetContext':self._target_context(a), 'tickSeconds':MOTOR_TICK_SECONDS,
                    'continuationTicks':CONTINUATION_TICKS,
                    'contract':'Choose an offered steering/pose intent; coordinates are host-owned. Free play is exploration, not a straight march: vary heading, curves, speed, and pose as you choose. Child directions and known taught patterns shape play. With a target, honor the requested relation: around/circle calls for AROUND steering, not repeated approach. STOP/NOOP pauses. Each choice permits at most six ticks; continuing needs a new choice. Child interruption cancels.'}
                kwargs = {'goal':dict(a.goal),'scene':scene,'actions':descriptions,
                          'turn':a.turns % DECISION_HORIZON + 1,'max_turns':DECISION_HORIZON}
                view={'goal':kwargs['goal'],'scene':scene,'turn':kwargs['turn'],'max_turns':kwargs['max_turns']}
                while len(json.dumps(view,sort_keys=True)) > 4000 and scene['known_patterns']:
                    scene['known_patterns'].pop()
                if len(json.dumps(view,sort_keys=True)) > 4000:
                    self.stop(a.subject,'jev-context-too-large')
                    return
                self.pending = a
                if self.threaded:
                    Thread(target=self._decision,args=(a,choices,kwargs),name='stickerbook-steering',daemon=True).start()
                    return
        if self.pending is not None and not self.threaded:
            self._decision(a,choices,kwargs)

    def _run(self):
        while not self.closed:
            self.pump()
            self.wake.wait(.03)
            self.wake.clear()
            with self.controller._world():
                if not self.activities and self.pending is None:
                    self.worker = None
                    return

    def close(self):
        self.closed = True
        self.stop(reason='host-stopped')
        self.wake.set()
