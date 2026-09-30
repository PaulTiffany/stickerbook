"""Execute actual conversation UI functions across pending/failure/page races."""
from pathlib import Path
import subprocess
import unittest

APP = Path(__file__).resolve().parents[1] / 'static/app.js'

class ConversationUI(unittest.TestCase):
    def test_pending_status_cleanup_and_late_reply_isolation(self):
        source = APP.read_text(encoding='utf-8')
        functions = source[source.index('function cancelConversationPresentation()'):source.index('function appendAccessibilityChatLine')]
        functions += source[source.index('function setVoiceOrbState('):source.index('async function captureVisualContext')]
        functions += source[source.index('async function acknowledgeConversation('):source.index('async function converseWithStickerBook(')]
        functions += source[source.index('async function converseWithStickerBook('):source.index('function startVoiceConversation(')]
        harness = r'''
const assert=require('node:assert/strict');
function node(){const classes=new Set();return {hidden:false,checked:false,setAttribute(){},classList:{add:x=>classes.add(x),remove:(...xs)=>xs.forEach(x=>classes.delete(x)),contains:x=>classes.has(x)}};}
const voiceOrb=node(),voiceOrbState=node(),conversationStatus=node(),voiceEnable=node(),agentAdultControls=node(),textChatEnable=node(),accessibilityChat=node(),accessibilityChatInput=node(),accessibilityChatSend=node(),voicePrivacyNote=node();
let voiceEnabled=true,voiceBusy=false,conversationPending=false,conversationSerial=0,voiceRecognition=null,textChatEnabled=true,motionEpoch=0;
let connected=false,calls=0,said=[],acknowledgeEnabled=false,ackCalls=0,ackResolve;
const screens={play:node()},window={SpeechRecognition:function(){}};
const conversationCapabilities=()=>({conversational_agent:connected,conversation_acknowledgement:acknowledgeEnabled});
const pendingPathObservation=Promise.resolve(),deicticReferenceSerial=0,pendingDeicticReference=null;
let capture=async()=>null;
const deicticPayload=()=>null,captureVisualContext=()=>capture(),clearDeicticReference=()=>{},appendAccessibilityChatLine=()=>{},speak=x=>said.push(x),DEV=false;
const observePoweredRequest=fn=>fn();
let resolve,reject;
const world={name:'local',converse:()=>{calls++;return new Promise((yes,no)=>{resolve=yes;reject=no;});}};
world.acknowledge=()=>{ackCalls++;return new Promise(yes=>{ackResolve=yes;});};
'''
        tail = r'''
(async()=>{
 updateConversationControls();assert.equal(voiceOrb.hidden,true);assert.equal(voiceEnabled,true);
 connected=true;updateConversationControls();assert.equal(voiceOrb.hidden,false);assert.equal(voiceEnable.checked,true);
 let request=converseWithStickerBook('hello',false,true);
 await new Promise(setImmediate);
 assert.equal(conversationStatus.hidden,false);assert.equal(voiceOrb.classList.contains('thinking'),true);assert.equal(voiceBusy,true);
 await converseWithStickerBook('duplicate',false,true);assert.equal(calls,1);
 resolve({ok:false,error:'omegallm-timeout'});await request;
 assert.equal(conversationStatus.hidden,true);assert.equal(voiceBusy,false);
 request=converseWithStickerBook('retry',false,true);await new Promise(setImmediate);
 resolve({ok:true,reply:'Hello!'});await request;assert.deepEqual(said,['Hello!']);assert.equal(voiceBusy,false);
 request=converseWithStickerBook('old page',false,true);await new Promise(setImmediate);const oldResolve=resolve;
 motionEpoch++;cancelConversationPresentation();assert.equal(conversationStatus.hidden,true);assert.equal(voiceBusy,false);
 const newer=converseWithStickerBook('new page',false,true);await new Promise(setImmediate);
 oldResolve({ok:true,reply:'Old reply'});await request;
 assert.deepEqual(said,['Hello!']);assert.equal(conversationPending,true);assert.equal(voiceBusy,true);
 resolve({ok:true,reply:'New reply'});await newer;
 assert.deepEqual(said,['Hello!','New reply']);assert.equal(conversationStatus.hidden,true);
 let utterance;
 global.SpeechSynthesisUtterance=class {constructor(text){this.text=text;}};
 window.speechSynthesis={cancel(){},speak:value=>{utterance=value;}};
 request=converseWithStickerBook('spoken',true,true);await new Promise(setImmediate);
 assert.equal(voiceOrb.classList.contains('thinking'),true);
 resolve({ok:true,reply:'Speaking now'});await request;
 assert.equal(voiceOrb.classList.contains('speaking'),true);assert.equal(voiceBusy,true);assert.equal(conversationStatus.hidden,true);
 utterance.onend();assert.equal(voiceBusy,false);assert.equal(accessibilityChatSend.disabled,false);
 request=converseWithStickerBook('voice timeout',true,true);await new Promise(setImmediate);
 resolve({ok:false,error:'omegallm-timeout'});await request;
 assert.equal(voiceBusy,false);assert.equal(conversationStatus.hidden,true);assert.equal(voiceOrb.classList.contains('error'),true);
 acknowledgeEnabled=true;
 const before=calls;
 request=converseWithStickerBook('parallel',false,true);await new Promise(setImmediate);
 assert.equal(calls,before+1);assert.equal(ackCalls,1);
 ackResolve({ok:true,reply:'Considering that request.'});await new Promise(setImmediate);
 assert.equal(said.at(-1),'Considering that request.');assert.equal(voiceBusy,true);
 resolve({ok:true,reply:'Final answer.'});await request;assert.equal(said.at(-1),'Final answer.');assert.equal(voiceBusy,false);
 request=converseWithStickerBook('late ack',false,true);await new Promise(setImmediate);
 const lateAck=ackResolve;resolve({ok:true,reply:'Fast final.'});await request;
 lateAck({ok:true,reply:'Too late'});await new Promise(setImmediate);assert.equal(said.at(-1),'Fast final.');
 world.acknowledge=async()=>{throw new Error('optional failure');};
 request=converseWithStickerBook('ack failure',false,true);await new Promise(setImmediate);
 resolve({ok:true,reply:'Still works.'});await request;assert.equal(said.at(-1),'Still works.');
 let ackSpeech;
 world.acknowledge=async()=>({ok:true,reply:'Considering your words.'});
 window.speechSynthesis.speak=value=>{ackSpeech=value;};
 request=converseWithStickerBook('voice ack',true,true);await new Promise(setImmediate);
 assert.equal(ackSpeech.text,'Considering your words.');assert.equal(voiceBusy,true);assert.equal(conversationPending,true);
 ackSpeech.onend();assert.equal(voiceOrb.classList.contains('thinking'),true);assert.equal(voiceBusy,true);
 resolve({ok:true,reply:'Real response.'});await request;ackSpeech.onend();assert.equal(voiceBusy,false);
 let finishCapture;capture=()=>new Promise(yes=>{finishCapture=yes;});
 const callsBeforeCapture=calls;
 request=converseWithStickerBook('leaving during image capture',false,true);await new Promise(setImmediate);
 motionEpoch++;cancelConversationPresentation();finishCapture(null);await request;
 assert.equal(calls,callsBeforeCapture);capture=async()=>null;
 voiceEnabled=false;updateConversationControls();assert.equal(voiceOrb.hidden,true);
 world.name='public mechanical';connected=false;updateConversationControls();assert.equal(voiceOrb.hidden,true);
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
        result = subprocess.run(['node', '-e', harness+functions+tail],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
