"""Threaded live-state reads remain independent of Jev think-time."""
import json
from pathlib import Path
import sys
import threading
import time
import unittest
import urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bridge

class MotorHttp(unittest.TestCase):
 def test_poll_during_choice_never_probes_health_or_blocks_child_grab(self):
  entered,release=threading.Event(),threading.Event()
  class Jev:
   probes=0
   def available(self): self.probes+=1;return True
   def choose(self,**kwargs):
    entered.set();release.wait(3)
    return {'ok':True,'choice':'MOVE:butterfly-1:CONTINUE+CLIP-flutter'}
  runtime=Jev();server,book=bridge.serve(port=0,quiet=True,jev_runtime=runtime,continuous_motion=True)
  worker=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True);worker.start()
  base='http://127.0.0.1:'+str(server.server_port)
  def call(path,body=None):
   req=urllib.request.Request(base+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
   with urllib.request.urlopen(req,timeout=1) as response:return json.load(response)
  try:
   call('/api/state');call('/api/animate',{'sticker':'butterfly-1','command_id':'tap'})
   self.assertTrue(entered.wait(1));probes=runtime.probes
   for _ in range(4):
    started=time.monotonic();state=call('/api/state?watch=1&page=farm')
    self.assertLess(time.monotonic()-started,.5);self.assertTrue(state['motion'])
   self.assertEqual(runtime.probes,probes)
   held=call('/api/hold',{'sticker':'butterfly-1'})
   self.assertTrue(held['ok']);self.assertEqual(held['state']['motion'],[])
   release.set();time.sleep(.1)
   self.assertEqual(call('/api/state?watch=1&page=farm')['revision'],2)
   self.assertFalse(call('/api/motion')['activities'])
  finally:
   release.set();book.close();server.shutdown();server.server_close();worker.join(1)
