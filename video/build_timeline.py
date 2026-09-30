"""Explicit musical edit: supplied words remain authoritative, timing is audited."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'video/data'

def main():
    lyrics=json.loads((D/'lyrics.json').read_text(encoding='utf-8'))
    # Editorial cue corrections for regions where music ASR did not match the
    # supplied lyrics. These are visual windows, not claims of forced alignment.
    overrides={}
    shots=[]
    for line in lyrics:
        actual_id=line['id'];i=actual_id if actual_id<=38 else actual_id-1
        start,end=line['start'],line['end']
        section=line['section']; text=line['text']; low=text.lower()
        scene='play';world='farm';subject='frog';title='';cameo=None
        if section=='Intro':scene=['cover','worlds','tray','hop'][i]; title=['OPEN THE BOOK','PICK A WORLD','PICK A STICKER','MAKE IT MOVE'][i]
        elif section=='Verse 1':
            if i in [4,5]:scene='flight';subject='bird' if i==5 else 'frog';title='WHAT IF IT COULD FLY?' if i==5 else ''
            if i in [6,7]:scene='drag';subject='cloud' if i==6 else 'fish';world='farm' if i==6 else 'school';title='DRAG. DROP. PLAY.'
            if i==8:scene='curve';cameo='ray-kurzweil';title='OFF THE PAGE'
            if i in [9,10]:scene='repair';cameo='aubrey-de-grey' if i==9 else None;title='REPAIR THE PAGE' if i==9 else 'ROOM TO PLAY. RULES TO STAY.'
            if i in [11,14]:world='theater';scene='ensemble';title='THE FUTURE GETS A STAGE'
            if i in [12,13]:scene='accelerate';cameo='david-orban' if i==12 else None;subject='bird';title='ANIMATE' if i==12 else 'ACCELERATE'
            if i in [15,16]:scene='hop';title='MAKE THE FROG HOP'
        elif section.startswith('Pre-Chorus'):
            scene='boundary';title=['GIVE IMAGINATION ROOM','TEACH IT. LET IT GROOVE.'][section.endswith('2')];world='playground'
        elif section.startswith('Chorus') or section=='Final Chorus':
            scene='chorus';title='P-HOP';world=['farm','beach','playground','school','space','theater'][i%6]
            if 'frog hop' in low:scene='hop';title='MAKE THE FROG HOP'
            elif 'bird fly' in low:scene='flight';subject='bird';title='MAKE THE BIRD FLY'
            elif 'eagleman' in low:scene='sense';cameo='david-eagleman';title='ANOTHER LITTLE SENSE'
            elif 'p-doom' in low or 'going up' in low:scene='meters';title='P-HOP UP / P-DOOM DOWN'
            elif 'tap it' in low or 'teach it' in low:scene='teach';title='SAY IT. TAP IT. TEACH IT.'
            if section=='Final Chorus':
                if actual_id in range(78,84):scene='worlds';title='SIX WORLDS. ONE BOOK.'
                if actual_id in [84,85]:scene='isolation';title='RESPONSES KNOW THEIR PLACE'
                if actual_id in [86,87]:scene='localhost';title='POWERED ON LOCALHOST'
                if actual_id in range(88,94):
                    scene='cameo';world='theater'
                    cameo=['ray-kurzweil','aubrey-de-grey','natasha-vita-more','ben-goertzel','david-eagleman','david-orban'][actual_id-88]
                    title=['RAY','AUBREY','NATASHA','BEN','EAGLEMAN','DAVID'][actual_id-88]
                if actual_id in range(94,98):scene='people-ensemble';world='theater';title='NOBODY KNOWS. EVERYBODY CAN PLAY.'
        elif section=='Post-Chorus':
            scene='cameo'
            cameo=['ray-kurzweil','aubrey-de-grey','david-eagleman','natasha-vita-more','ben-goertzel','max-more',None,None][actual_id-31]
            world=['playground','beach','school','theater','space','beach','farm','farm'][actual_id-31]
            title=['RAY','AUBREY','EAGLEMAN','NATASHA','BEN','MAX','EVERY WORLD HAS A PLACE','A CLEARLY MARKED DOOR'][actual_id-31]
        elif section=='Verse 2':
            scene='pipeline';title='OMEGA → JEV → HOST'
            if i==38:scene='proof-language';title='REAL LANGUAGE / BOUNDED GOAL'
            if i in [40,41]:scene='compress';title='MEANING BECOMES A LEGAL CHOICE'
            if i in [42,43]:scene='choices';title='MOVE / FACE / ANIMATE / NOOP'
            if i in [44,45]:scene='proof-double';subject='butterfly';title='DOUBLE TAP → JEV'
            if i in [46,47]:scene='teach';title='TEACH A PATTERN. RECALL THE GROOVE.'
            if i in [48,49]:scene='memory';title='MEMORY SUGGESTS. IT DOES NOT COMMAND.'
            if i==50:scene='proof-human';subject='butterfly';title='THE CHILD KEEPS THE HAND'
        elif section=='Bridge':
            scene='shell';title='FREEDOM WITH A BOUNDARY';cameo='eliezer-yudkowsky' if i in [65,67,68] else None
            if i in [69,70]:title='OPENSHELL: THE HARDENED TARGET'
            if i in [71,72,73,74]:title='LOCAL DEV: RESTRICTED DOCKER'
        elif section=='Outro':scene='outro';title='HOP!' if i==110 else 'ONE BOOK. MANY WORLDS.'
        shots.append({'id':actual_id,'start':start,'end':end,'scene':scene,'world':world,'subject':subject,'title':title,'cameo':cameo,
                      'lyric':text,'section':section,'timing': 'editorial visual cue; uncertain ASR match' if i in overrides else 'matched vocal cue',
                      'confidence':line['alignment_confidence']})
    for n,shot in enumerate(shots[:-1]):
        shot['end']=min(shot['end'],shots[n+1]['start'])
    # Fill instrumental intro/short gaps with the previous picture; shot changes
    # stay anchored to vocals, motion accents to measured beat times.
    # Preserve motion across adjacent cues belonging to one visual shot.
    groups=[]
    for shot in shots:
        key=tuple(shot[k] for k in ['scene','world','title','cameo'])
        if groups and groups[-1][0]==key:groups[-1][1].append(shot)
        else:groups.append((key,[shot]))
    for _,group in groups:
        for shot in group:
            shot['visual_start']=group[0]['start'];shot['visual_end']=group[-1]['end']
    (D/'timeline.json').write_text(json.dumps(shots,indent=2),encoding='utf-8',newline='\n')
    print('Built',len(shots),'explicit lyric/visual cues')

if __name__=='__main__':main()
