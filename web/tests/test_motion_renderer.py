"""Exercise the actual renderer functions with a deterministic SVG/frame harness."""
import json
from pathlib import Path
import subprocess
import unittest

APP = Path(__file__).resolve().parents[1] / 'static/app.js'
HARNESS = r'''
const assert = require('node:assert/strict');
class Node {
 constructor(){this.attrs={};this.children=[];this.classList={add(){},remove(){}};this.listeners={};}
 setAttribute(k,v){this.attrs[k]=v;} addEventListener(k,v){this.listeners[k]=v;}
 appendChild(n){this.children.push(n);} replaceChildren(...n){this.children=n;}
 remove(){this.removed=true;}
}
let now=0, serial=0, frames=new Map(), receipts=0;
const performance={now:()=>now};
const requestAnimationFrame=(f)=>{frames.set(++serial,f);return serial;};
const cancelAnimationFrame=(id)=>frames.delete(id);
function advance(ms){now+=ms; const pending=[...frames.values()];frames.clear();for(const f of pending)f(now);}
const layers={stickers:new Node()};
const el=()=>new Node(), stickerNode=()=>new Node(), stickerClip=()=>({});
const activePageMetrics=()=>({width:1000,height:640});
const kernelWorld={},world=kernelWorld;
let state={page:{id:'farm'},revision:1,stickers:[]};
const render=()=>drawStickers(state.stickers);
const sticker=(x,y=.5)=>({id:'bird-1',definition:'bird',x,y,animation:'flap',scale:1});
const snapshot=(revision,x)=>({page:{id:'farm'},revision,stickers:[sticker(x)]});
'''

class MotionRenderer(unittest.TestCase):
 def test_identity_endpoints_intermediate_frames_hold_page_and_stale_observation(self):
  source=APP.read_text(encoding='utf-8')
  functions=source[source.index('// Authoritative endpoints stay'):source.index('\nfunction definitionIds()')]
  tail=r'''
applyAuthoritativeState(snapshot(1,.5));
const visual=stickerVisuals.get('bird-1'), node=visual.node, art=node.children[0];
applyAuthoritativeState(snapshot(2,.56)); advance(110);
assert(visual.position.x>.5 && visual.position.x<.56);
assert.equal(state.stickers[0].x,.56); // Frames are not world facts.
advance(110);assert.equal(visual.position.x,.56);
applyAuthoritativeState(snapshot(3,.62)); advance(220);
assert.equal(visual.position.x,.62);
assert.equal(visual.node,node);assert.equal(node.children[0],art);
assert.equal(receipts,0); // No mutation calls exist in this rendering path.
assert.equal(applyAuthoritativeState(snapshot(2,.56)),false);
applyAuthoritativeState(snapshot(4,.68));advance(60);
cancelStickerTween(visual);visual.held=true;
const held={...visual.position};applyAuthoritativeState(snapshot(5,.74));advance(500);
assert.deepEqual(visual.position,held);assert.equal(frames.size,0);
visual.held=false;cancelVisualMotion();
assert.equal(applyAuthoritativeState(snapshot(6,.8),0),false);
assert.equal(applyAuthoritativeState({...snapshot(6,.8),page:{id:'beach'}}),false);
console.log(JSON.stringify({ok:true,endpoints:[.5,.56,.62],stableIdentity:true}));
'''
  completed=subprocess.run(['node','-e',HARNESS+functions+tail],capture_output=True,text=True)
  self.assertEqual(completed.returncode,0,completed.stderr)
  self.assertTrue(json.loads(completed.stdout)['ok'])
