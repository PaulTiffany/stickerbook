"""Explicit musical edit: supplied words remain authoritative, timing is audited."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'video/data'

def main():
    lyrics=json.loads((D/'lyrics.json').read_text())
    # Editorial cue corrections for regions where music ASR did not match the
    # supplied lyrics. These are visual windows, not claims of forced alignment.
    overrides={31:(61.74,62.9),32:(62.9,64.1),33:(64.1,66.3),34:(66.5,68),35:(68,70.1),36:(70.1,72.8),37:(72.8,75.68),
               60:(119.26,121.9),61:(121.9,122.84)}
    # Do not stack unmatched tail lyrics at one ASR timestamp. Stage the visual
    # ideas in measured final-chorus/outro windows while preserving source text.
    tail=[(87,160.5),(88,161.7),(89,162.9),(90,164.1),(91,165.3),(92,166.5),(93,167.7),(94,168.9),
          (95,170.24),(96,171.38),(97,172.62),(98,173.82),(99,176.48),(100,177.36)]
    for (i,t),(j,end) in zip(tail,tail[1:]):overrides[i]=(t,end)
    overrides[100]=(177.36,178.4)
    for i in range(101,110):overrides[i]=(178.4,179.55)
    overrides[110]=(179.55,179.84)
    shots=[]
    for line in lyrics:
        i=line['id'];start,end=overrides.get(i,(line['start'],line['end']))
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
                if i in range(77,83):scene='worlds';title='SIX WORLDS. ONE BOOK.'
                if i in [83,84,89,90]:scene='isolation';title='RESPONSES KNOW THEIR PLACE'
                if i in [85,86]:scene='localhost';title='POWERED ON LOCALHOST'
                if i in [87,88]:scene='memory';title='EACH WORLD KEEPS ITS STATE'
                if i in [91,92,93,94]:scene='pipeline';title='LANGUAGE → CHOICE → RECEIPT'
                if i in [95,96,97,98]:scene='ensemble';title='START SMALL. LET IT PLAY.'
        elif section=='Post-Chorus':
            scene='cameo';cameo={31:'natasha-vita-more',32:'max-more',33:'ben-goertzel'}.get(i)
            world={31:'playground',32:'beach',33:'space',34:'theater',35:'space',36:'school',37:'farm'}[i]
            title={31:'NATASHA',32:'MAX',33:'BEN'}.get(i,'EVERY WORLD HAS A PLACE')
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
        shots.append({'id':i,'start':start,'end':end,'scene':scene,'world':world,'subject':subject,'title':title,'cameo':cameo,
                      'lyric':text,'section':section,'timing': 'editorial visual cue; uncertain ASR match' if i in overrides else 'matched vocal cue',
                      'confidence':line['alignment_confidence']})
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
