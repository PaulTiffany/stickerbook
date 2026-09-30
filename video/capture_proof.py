"""Capture real host/kernel evidence with isolated page worlds and live agents.

Does not touch the child's running bridge or its page state. Agent requests use
the existing loopback containers. No credentials or provider logs are captured.
"""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'web'))
from bridge import BookBridge
from agent_runtime import LoopbackAgentRuntime
from jev_runtime import LoopbackJevRuntime

def project(value):
    """Keep observed state/evidence, omit repeated unused sticker catalogs."""
    if isinstance(value,list):return [project(v) for v in value]
    if isinstance(value,dict):
        if 'revision' in value and 'stickers' in value:
            return {k:project(value[k]) for k in ['revision','principal','page','stickers','motion','capabilities'] if k in value}
        return {k:project(v) for k,v in value.items()}
    return value

def main():
    b=BookBridge(agent_runtime=LoopbackAgentRuntime('http://127.0.0.1:8761'),
                 jev_runtime=LoopbackJevRuntime('http://127.0.0.1:8762'),continuous_motion=True)
    evidence={'kind':'actual-live-runtime-evidence','captured_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
              'architecture':'Isolated host BookBridge worlds -> existing loopback Omega containers -> ordinary kernel receipts',
              'presentation':'Reconstructed from accepted receipts; not screen capture; original inference latency is time-compressed in the music edit', 'proofs':[]}
    def save():
        (ROOT/'video/data/proof.json').write_text(json.dumps(project(evidence),indent=2),encoding='utf-8',newline='\n')
    try:
        b.select_page({'page':'farm'})
        added=b.place({'asset':'butterfly','command_id':'video-place','point':{'x':.38,'y':.45}})
        sticker=added['receipt']['object']; print('Placed',sticker,flush=True)
        start=time.monotonic()
        invited=b.animate({'sticker':sticker,'command_id':'video-double-tap'})
        snapshots=[]
        while time.monotonic()-start<9:
            state=b.state(fast=True,observing_page='farm')
            if not snapshots or state['revision']!=snapshots[-1]['state']['revision']:
                snapshots.append({'elapsed':round(time.monotonic()-start,3),'state':state})
            time.sleep(.12)
        before=b.state(fast=True)
        held=b.hold({'sticker':sticker})
        audit=b.motion_audit()
        evidence['proofs'].append({'id':'double-tap','page':'farm','subject':sticker,'invitation':invited,
                                   'snapshots':snapshots,'audit':audit,'elapsed':round(time.monotonic()-start,3),
                                   'translated_by':None,'receipts':b.receipts()})
        save();print('Double tap evidence saved',flush=True)
        moved=b.propose_move({'sticker':sticker,'command_id':'video-child-move','point':{'x':.68,'y':.52}})
        time.sleep(2)
        evidence['proofs'].append({'id':'human-hand','hold':held,'move':moved,'after':b.state(fast=True),'audit':b.motion_audit()})
        farm=b.state(fast=True)
        space=b.select_page({'page':'space'})
        restored=b.select_page({'page':'farm'})
        evidence['proofs'].append({'id':'page-isolation','farm':farm,'space':space,'restored':restored})
        save();print('Human and page proof saved',flush=True)
        start=time.monotonic()
        answer=b.converse({'text':'Make the butterfly flutter.','input_mode':'text'})
        evidence['proofs'].append({'id':'language','utterance':'Make the butterfly flutter.','elapsed':round(time.monotonic()-start,3),'response':answer})
        save();print('Language result',answer.get('ok'),answer.get('error'),flush=True)
    finally:
        b.close()

if __name__=='__main__':main()
