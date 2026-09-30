"""Finite steering, per-tick receipts and child-revoked continuing invitations."""
import json
from pathlib import Path
import sys
import threading
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bridge
from motion_player import CONTINUATION_TICKS, MOTOR_TICK_SECONDS, OBSERVER_LEASE_SECONDS
from test_bridge import FakeAgentRuntime

class Chooser:
 def __init__(self): self.calls=[];self.choice='MOVE:butterfly-1:E+CLIP-flutter';self.hook=None
 def available(self): return True
 def choose(self,**kwargs):
  self.calls.append(kwargs)
  if self.hook: self.hook(kwargs)
  choice=self.choice
  if choice == 'MOVE:butterfly-1:E+CLIP-flutter' and choice not in kwargs['actions']:
   choice='MOVE:butterfly-1:E'
  return choice if isinstance(choice,dict) else {'ok':True,'choice':choice}

class Body(unittest.TestCase):
 def setUp(self):
  self.jev=Chooser();self.now=100.0
  self.b=bridge.Bridge(jev_runtime=self.jev,continuous_motion=True,motion_threaded=False)
  self.p=self.b.motion_player;self.p.clock=lambda:self.now
 def tearDown(self): self.p.close()
 def start(self):
  result=self.b.animate({'sticker':'butterfly-1','command_id':'tap'})
  self.assertTrue(result['ok']);self.assertEqual(result['jev']['result'],'playing')
  self.p.pump();return result
 def advance(self,n=1):
  for _ in range(n):
   self.now+=MOTOR_TICK_SECONDS;self.p.observe();self.p.pump()
 def receipts(self): return [e for e in self.p.audit if e['kind']=='receipt']
 def test_clip_and_travel_coexist_with_finite_subject_only_surface(self):
  self.start();self.advance()
  sticker=self.b.kernel.sticker('butterfly-1')
  self.assertGreater(sticker.x,.52);self.assertEqual(sticker.animation,'flutter')
  call=self.jev.calls[0];keys=call['actions']
  self.assertIn('MOVE:butterfly-1:LEFT-SMALL',keys)
  self.assertIn('MOVE:butterfly-1:RIGHT-LARGE+CLIP-flutter',keys)
  self.assertIn('FACE:butterfly-1:LEFT',keys)
  self.assertIn('ANIMATE:butterfly-1:flutter',keys)
  self.assertIn('NOOP',keys);self.assertIn('STOP',keys)
  self.assertFalse(any('cow-1' in k or k.startswith('RESIZE:') for k in keys))
  self.assertEqual(call['scene']['motion']['continuationTicks'],CONTINUATION_TICKS)
  for e in self.receipts():
   self.assertTrue(e['receipt']['accepted']);self.assertEqual(e['receipt']['requestedBy'],'human:kid')
   self.assertIsNone(e['receipt']['translatedBy']);self.assertEqual(e['receipt']['selectedBy'],'agent:jev-visual-1')
 def test_one_steering_choice_cannot_exceed_continuation_budget(self):
  self.start();a=self.p.activities['butterfly-1'];a.next_decision=1000
  self.advance(CONTINUATION_TICKS+3)
  moves=[e for e in self.receipts() if e['receipt']['action']=='move-sticker']
  self.assertEqual(len(moves),CONTINUATION_TICKS)
  self.assertEqual(len(self.jev.calls),1)
  self.assertAlmostEqual(self.b.kernel.sticker('butterfly-1').x,.52+.055*MOTOR_TICK_SECONDS*CONTINUATION_TICKS)
 def test_curved_course_and_context_come_from_accepted_motor_deltas(self):
  self.start();self.advance()
  self.jev.choice='MOVE:butterfly-1:RIGHT-SMALL'
  self.advance(3)
  moves=[e['position'] for e in self.receipts() if e['receipt']['action']=='move-sticker']
  self.assertGreater(moves[-1]['y'],moves[0]['y'])
  self.assertGreater(self.jev.calls[-1]['scene']['motion']['heading'],0)
  self.assertNotEqual(self.jev.calls[-1]['scene']['motion']['lastDelta'],{'dx':0.0,'dy':0.0})
  slopes=[round((q['y']-p['y'])/(q['x']-p['x']),3) for p,q in zip(moves,moves[1:]) if q['x']!=p['x']]
  self.assertGreater(len(set(slopes)),1)
 def test_unknown_key_and_model_coordinates_are_not_authority(self):
  self.jev.choice={'ok':True,'choice':'MOVE:butterfly-1:E+CLIP-flutter','point':{'x':.99,'y':.99}}
  self.start();self.advance()
  self.assertAlmostEqual(self.b.kernel.sticker('butterfly-1').x,.52+.055*MOTOR_TICK_SECONDS)
  self.assertAlmostEqual(self.b.kernel.sticker('butterfly-1').y,.38)
  self.jev.choice='MOVE:butterfly-1:ARBITRARY-.99-.99';self.advance()
  self.assertFalse(self.p.activities)
  self.assertEqual(self.p.audit[-1]['reason'],'unknown-jev-choice')
 def test_non_string_choice_fails_closed_and_is_not_reflected(self):
  self.jev.choice={'ok':True,'choice':{'secret':'never reflect'}}
  self.start();self.assertFalse(self.p.activities)
  self.assertNotIn('never reflect',json.dumps(list(self.p.audit)))
 def test_noop_stops_continuation_but_cannot_restart_without_a_new_decision(self):
  self.start();self.jev.choice='NOOP';self.advance()
  a=self.p.activities['butterfly-1'];self.assertEqual(a.remaining,0)
  count=len(self.receipts());position=self.b.kernel.sticker('butterfly-1')
  self.advance(2);self.assertEqual(len(self.receipts()),count)
  self.assertEqual(self.b.kernel.sticker('butterfly-1'),position)
  self.assertIn('butterfly-1',self.p.activities) # Child invitation survives the pause.
 def test_grab_revokes_without_any_world_mutation_and_late_choice_is_ignored(self):
  entered,release=threading.Event(),threading.Event()
  self.jev.hook=lambda _: (entered.set(),release.wait(3))
  self.b.animate({'sticker':'butterfly-1','command_id':'tap'})
  worker=threading.Thread(target=self.p.pump);worker.start();self.assertTrue(entered.wait(2))
  revision=self.b.kernel.revision
  self.assertTrue(self.b.hold({'sticker':'butterfly-1'})['ok'])
  release.set();worker.join(3);self.assertFalse(worker.is_alive())
  self.assertEqual(self.b.kernel.revision,revision);self.assertFalse(self.p.activities)
  self.p.observe();self.p.pump();self.assertEqual(len(self.jev.calls),1)
 def test_same_subject_child_movement_supersedes_no_retry_different_subject_does_not(self):
  self.jev.hook=lambda _: self.b.propose_move({'sticker':'cow-1','command_id':'cow','point':{'x':.2,'y':.7}})
  self.start();self.advance();self.assertIn('butterfly-1',self.p.activities)
  self.jev.hook=lambda _: self.b.propose_move({'sticker':'butterfly-1','command_id':'child','point':{'x':.3,'y':.6}})
  before=len(self.jev.calls);self.advance()
  self.assertFalse(self.p.activities);self.p.pump();self.assertEqual(len(self.jev.calls),before+1)
  self.assertAlmostEqual(self.b.kernel.sticker('butterfly-1').x,.3)
  self.assertTrue(any(e.get('reason')=='human-superseded' for e in self.p.audit))
 def test_subject_mutation_without_provenance_fails_closed(self):
  self.start()
  from stickerbook_core import Command,MOVE_STICKER
  self.b.kernel.propose(Command(MOVE_STICKER,'human:kid','external',object_id='butterfly-1',params=(('x',.8),('y',.8))))
  self.advance();self.assertFalse(self.p.activities)
  self.assertEqual(self.p.audit[-1]['reason'],'stale-subject')
 def test_observer_departure_cancels_and_observation_cannot_restart(self):
  self.start();self.now+=OBSERVER_LEASE_SECONDS+.01;self.p.pump()
  self.assertFalse(self.p.activities);self.p.observe();self.p.pump()
  self.assertEqual(len(self.jev.calls),1)
 def test_child_taught_patterns_remain_bounded_advisory(self):
  from pattern_memory import PatternStep
  self.b.patterns.remember(label='happy swoop',asset='butterfly',steps=(PatternStep('MOVE','STEP-NE'),),subject_id='butterfly-1',learned_by='human:kid',revision=2)
  self.start();patterns=self.jev.calls[0]['scene']['known_patterns']
  self.assertEqual(patterns[0]['label'],'happy swoop');self.assertLessEqual(len(patterns),8)
  self.assertNotIn('MOVE:butterfly-1',json.dumps(patterns));self.assertNotIn('transcript',self.jev.calls[0]['scene'])
 def test_animation_redirection_preserves_heading_and_target_but_replaces_old_invitation(self):
  self.p.start({'subject':'butterfly-1','intent':'control','behavior':'circle','target':{'kind':'point','x':.6,'y':.2}},actor='human:kid',requested_by='human:kid')
  old=self.p.activities['butterfly-1'];old.heading=7
  self.p.start({'subject':'butterfly-1','intent':'animate','behavior':'flutter'},actor='human:kid',requested_by='human:kid',translated_by='agent:omega-llm')
  new=self.p.activities['butterfly-1'];self.assertIsNot(old,new)
  self.assertEqual(new.heading,7);self.assertEqual(new.goal['target'],old.goal['target'])

 def test_relative_target_is_a_bounded_sensing_primitive_not_a_model_coordinate(self):
  self.p.start({'subject':'butterfly-1','intent':'control','behavior':'circle',
                'target':{'kind':'point','x':.52,'y':.20}},actor='human:kid',requested_by='human:kid')
  self.jev.choice='MOVE:butterfly-1:AROUND-LEFT+CLIP-flutter';self.p.pump()
  self.p.activities['butterfly-1'].next_decision=1000
  self.advance(CONTINUATION_TICKS)
  moves=[e for e in self.receipts() if e['receipt']['action']=='move-sticker']
  self.assertEqual(len(moves),CONTINUATION_TICKS)
  self.assertLess(moves[-1]['position']['x'],moves[0]['position']['x'])
  self.assertLess(moves[-1]['position']['y'],moves[0]['position']['y'])
  call=self.jev.calls[0];self.assertIn('AROUND-LEFT',','.join(call['actions']))
  self.assertIsNotNone(call['scene']['motion']['targetContext'])
  self.assertTrue(all(e['receipt']['accepted'] for e in moves))
 def test_body_ticks_do_not_become_misleading_discrete_pattern_steps(self):
  self.start();self.advance()
  result=self.b.jev_controller.remember_recent(subject_id='butterfly-1',
       label='continuous swoop',learned_by='human:kid')
  self.assertFalse(result['ok']);self.assertEqual(result['error'],'no-accepted-pattern-steps')
 def test_previous_language_turn_cannot_restart_after_a_child_grab(self):
  entered,release=threading.Event(),threading.Event()
  llm=FakeAgentRuntime()
  def converse(**_):
   entered.set();release.wait(3)
   return {'ok':True,'reply':'Flying now.','goal':{'subject':'butterfly-1','intent':'control','behavior':'fly'}}
  llm.converse=converse
  self.b.agent_runtime=llm;self.b._inference_selection={'provider':'asicloud','model':'minimax/minimax-m3'}
  results=[];worker=threading.Thread(target=lambda:results.append(self.b.converse({'text':'fly'})))
  worker.start();self.assertTrue(entered.wait(2));self.b.hold({'sticker':'butterfly-1'})
  release.set();worker.join(3)
  self.assertEqual(results[0]['jev']['error'],'human-superseded')
  self.assertFalse(self.p.activities)
 def test_late_admission_version_is_checked_atomically(self):
  self.b.hold({'sticker':'butterfly-1'})
  result=self.p.start({'subject':'butterfly-1','intent':'control'},
      actor='human:kid',requested_by='human:kid',expected_child_version=0)
  self.assertEqual(result['error'],'human-superseded');self.assertFalse(self.p.activities)

 def test_real_decisions_contract_accepts_target_scene_with_bounded_pattern_context(self):
  from pattern_memory import PatternStep
  for index in range(8):
   self.b.patterns.remember(label=('swoop '+str(index)+' ??')*4,asset='butterfly',
    steps=tuple(PatternStep('MOVE','STEP-NE') for _ in range(12)),
    subject_id='butterfly-1',learned_by='human:kid',revision=2)
  self.p.start({'subject':'butterfly-1','intent':'control','behavior':'swoop',
    'target':{'kind':'point','x':.775,'y':.635}},actor='human:kid',requested_by='human:kid')
  self.jev.choice='MOVE:butterfly-1:TOWARD-TARGET+CLIP-flutter';self.p.pump()
  call=self.jev.calls[0]
  sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'jev/omega_jev/providers'))
  from jev_core import build_request
  view={k:call[k] for k in ('goal','scene','turn','max_turns')}
  request=build_request(view,'typesafe/jev-1.13',actions={k:'sb-return' for k in call['actions']},criteria=call['actions'],instructions='Choose one offered steering intent for the child goal, with the current motor context.')
  self.assertLessEqual(len(json.dumps(request['state'],sort_keys=True)),4000)
  self.assertTrue(call['scene']['known_patterns'])
  self.assertTrue(all(p['stepsOmitted']==10 for p in call['scene']['known_patterns']))

 def test_hold_supplies_fresh_revision_so_the_child_release_is_not_blocked_by_old_observation(self):
  self.start();old_revision=self.b.kernel.revision;self.advance()
  self.assertGreater(self.b.kernel.revision,old_revision)
  held=self.b.hold({'sticker':'butterfly-1'})
  result=self.b.propose_move({'sticker':'butterfly-1','command_id':'child-release',
       'based_on_revision':held['state']['revision'],'point':{'x':.3,'y':.6}})
  self.assertTrue(result['receipt']['accepted']);self.assertFalse(self.p.activities)
  self.assertAlmostEqual(self.b.kernel.sticker('butterfly-1').x,.3)

 def test_grab_also_cancels_a_pending_finite_pose_decision(self):
  entered,release=threading.Event(),threading.Event()
  self.jev.choice='ANIMATE:butterfly-1:flutter';self.jev.hook=lambda _: (entered.set(),release.wait(3))
  results=[]
  worker=threading.Thread(target=lambda:results.append(self.b.jev_controller.run_goal(
    {'subject':'butterfly-1','intent':'animate','behavior':'flutter'},actor='human:kid',
    command_prefix='pose',requested_by='human:kid',animate_only=True,max_turns=1)))
  worker.start();self.assertTrue(entered.wait(2));revision=self.b.kernel.revision
  self.b.hold({'sticker':'butterfly-1'});release.set();worker.join(3)
  self.assertEqual(results[0]['error'],'human-superseded');self.assertEqual(self.b.kernel.revision,revision)

 def test_every_existing_asset_fits_the_actual_rpc_action_count_limit(self):
  import governed_world
  from stickerbook_core import StickerInstance
  for asset in governed_world.ASSETS:
   subject='catalog-'+asset
   self.b.kernel.place_sticker(StickerInstance(subject,'human:kid','human:kid',asset,self.b.kernel.page,x=.5,y=.5,animation='rest'))
   result=self.p.start({'subject':subject,'intent':'control','target':{'kind':'point','x':.7,'y':.6}},actor='human:kid',requested_by='human:kid')
   self.assertTrue(result['ok'])
   choices,_=self.p.choices(self.p.activities[subject])
   self.assertLessEqual(len(choices),128)
   self.assertFalse(any(k.startswith('SCALE:') for k in choices))
   self.p.stop(subject)

class PageBody(unittest.TestCase):
 def test_page_switch_cancels_and_isolates_even_after_immediate_return(self):
  jev=Chooser();b=bridge.BookBridge(jev_runtime=jev,continuous_motion=True,motion_threaded=False)
  try:
   b.animate({'sticker':'butterfly-1','command_id':'tap'})
   old=b.motion_player;old.pump();before=b.kernel.revision
   b.select_page({'page':'beach'});self.assertEqual(b.motion_audit()['activities'],[])
   b.select_page({'page':'farm'});old.pump()
   self.assertEqual(b.kernel.revision,before);self.assertFalse(old.activities)
   self.assertFalse(b.hold({'_page':'beach','sticker':'butterfly-1'})['ok'])
  finally:b.close()
 def test_explicit_settling_direction_revokes_ongoing_player(self):
  llm=FakeAgentRuntime();llm.converse=lambda **_: {'ok':True,'reply':'Landing now.','goal':{'subject':'butterfly-1','intent':'animate','behavior':'land'}}
  jev=Chooser();b=bridge.Bridge(agent_runtime=llm,jev_runtime=jev,continuous_motion=True,motion_threaded=False)
  b.animate({'sticker':'butterfly-1','command_id':'tap'});b.motion_player.pump()
  jev.choice='ANIMATE:butterfly-1:land'
  result=b.converse({'text':'Have it land.'})
  self.assertTrue(result['jev']['ok']);self.assertFalse(b.motion_player.activities)
  self.assertEqual(b.kernel.sticker('butterfly-1').animation,'land');b.motion_player.close()

 def test_explicit_scale_goal_keeps_the_existing_finite_resize_contract(self):
  llm=FakeAgentRuntime();llm.converse=lambda **_: {'ok':True,'reply':'A little bigger.','goal':{'subject':'butterfly-1','intent':'control','scale':1.02}}
  jev=Chooser()
  def choose(**kwargs):
   jev.calls.append(kwargs)
   return {'ok':True,'choice':'SCALE:butterfly-1:UP' if len(jev.calls)==1 else 'NOOP'}
  jev.choose=choose
  b=bridge.Bridge(agent_runtime=llm,jev_runtime=jev,continuous_motion=True,motion_threaded=False)
  try:
   b.animate({'sticker':'butterfly-1','command_id':'tap'})
   result=b.converse({'text':'Make the butterfly a little bigger.'})
   self.assertTrue(result['jev']['ok']);self.assertFalse(b.motion_player.activities)
   self.assertAlmostEqual(b.kernel.sticker('butterfly-1').scale,1.02)
  finally:b.motion_player.close()

 def test_malformed_semantic_subject_fails_closed_without_starting_or_revoking_a_body(self):
  llm=FakeAgentRuntime();llm.converse=lambda **_: {'ok':True,'reply':'Trying.','goal':{'subject':{},'intent':'control'}}
  b=bridge.Bridge(agent_runtime=llm,jev_runtime=Chooser(),continuous_motion=True,motion_threaded=False)
  try:
   result=b.converse({'text':'Try'})
   self.assertEqual(result['jev']['error'],'missing-jev-subject');self.assertFalse(b.motion_player.activities)
  finally:b.motion_player.close()

 def test_land_at_a_visual_target_is_not_the_land_in_place_shortcut(self):
  llm=FakeAgentRuntime()
  goal={'subject':'butterfly-1','intent':'move-and-animate','behavior':'land',
        'target':{'kind':'point','x':.3,'y':.2}}
  llm.converse=lambda **_: {'ok':True,'reply':'Toward the roof.','goal':goal}
  b=bridge.Bridge(agent_runtime=llm,jev_runtime=Chooser(),continuous_motion=True,motion_threaded=False)
  try:
   result=b.converse({'text':'Land on top of the barn.'})
   self.assertEqual(result['jev']['result'],'playing')
   self.assertEqual(b.motion_player.activities['butterfly-1'].goal,goal)
   self.assertEqual(b.kernel.sticker('butterfly-1').animation,'rest')
  finally:b.motion_player.close()

 def test_recent_steering_is_bounded_motor_evidence_not_executable_history(self):
  b=bridge.Bridge(jev_runtime=Chooser(),continuous_motion=True,motion_threaded=False)
  now=[100.0];p=b.motion_player;p.clock=lambda:now[0]
  try:
   b.animate({'sticker':'butterfly-1','command_id':'tap'})
   for _ in range(20):
    now[0]+=.25;p.observe();p.pump()
   context=p.activities['butterfly-1'].describe()['recentSteeringHeadings']
   self.assertEqual(len(context),6)
   self.assertTrue(all(type(h) is int and 0<=h<16 for h in context))
   self.assertNotIn('MOVE:',json.dumps(context))
  finally:p.close()
