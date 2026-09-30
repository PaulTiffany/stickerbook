"""Deterministic sticker-paper music video, frame = render(master time).

No app changes, browser automation, model calls or simulation during rendering.
"""
import argparse,base64,bisect,hashlib,json,math,subprocess,time
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import xml.etree.ElementTree as ET
from concurrent.futures import ProcessPoolExecutor
from collections import deque
import cairosvg
from PIL import Image,ImageDraw,ImageFont,ImageFilter

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/'video'
W,H=1920,1080
INK='#222336';PINK='#ea4bad';BLUE='#395ec9';GREEN='#247d65';PAPER='#fff9eb';YELLOW='#ffd351'
MANIFEST=json.loads((ROOT/'web/static/assets/manifest.json').read_text())
AUDIO=json.loads((HERE/'data/audio.json').read_text())
TIMELINE=json.loads((HERE/'data/timeline.json').read_text())
PROOF=json.loads((HERE/'data/proof.json').read_text())
PAGES=['farm','beach','playground','school','space','theater']
STARTS=[s['start'] for s in TIMELINE]

def clamp(x):return max(0,min(1,x))
def ease(x):x=clamp(x);return x*x*(3-2*x)
def lerp(a,b,x):return a+(b-a)*x

@lru_cache(maxsize=128)
def font(size,mono=False):
    f=ImageFont.truetype(str(HERE/'input/fonts'/('JetBrainsMono.ttf' if mono else 'Fredoka.ttf')),size)
    if not mono:f.set_variation_by_axes([600,100])
    return f

def text(im,s,x,y,size=64,color=INK,anchor='mm',width=None,mono=False,stroke=0):
    if not mono:s=s.replace('→',' / ').replace('≠','IS NOT')
    d=ImageDraw.Draw(im)
    if width:
        while size>14 and d.textlength(s,font=font(size,mono))>width:size-=2
    d.text((round(x),round(y)),s,font=font(size,mono),fill=color,anchor=anchor,stroke_width=stroke,stroke_fill=PAPER)

def pill(im,s,x,y,color=PINK,size=28):
    s=s.replace('→',' / ').replace('≠','IS NOT')
    f=font(size);d=ImageDraw.Draw(im);width=d.textlength(s,font=f)+40
    d.rounded_rectangle((x-width/2,y-25,x+width/2,y+25),radius=25,fill=color)
    text(im,s,x,y,size,'white')

@lru_cache(maxsize=64)
def background(world,width=1792,height=670):
    src=ROOT/'web'/MANIFEST['pages'][world]['variants']['landscape']['src']
    im=Image.open(BytesIO(cairosvg.svg2png(url=str(src),output_width=width))).convert('RGBA')
    # Preserve the original artwork's aspect ratio and crop only if needed.
    canvas=Image.new('RGBA',(width,height),PAPER)
    if im.height>height:
        scale=height/im.height;im=im.resize((round(im.width*scale),height),Image.Resampling.LANCZOS)
    canvas.alpha_composite(im,((width-im.width)//2,(height-im.height)//2))
    mask=Image.new('L',canvas.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,width-1,height-1),radius=28,fill=255)
    canvas.putalpha(mask)
    return canvas

@lru_cache(maxsize=256)
def pose_image(asset,pose):
    src=ROOT/'web'/MANIFEST['stickers'][asset]['sprites'][pose]
    element=ET.parse(src).getroot().find('{http://www.w3.org/2000/svg}image')
    return Image.open(BytesIO(base64.b64decode(element.get('href').split(',',1)[1]))).convert('RGBA')

@lru_cache(maxsize=400)
def sticker_image(asset,pose,size,angle):
    raw=pose_image(asset,pose).resize((size,size),Image.Resampling.LANCZOS)
    if angle:raw=raw.rotate(angle,Image.Resampling.BICUBIC,expand=True)
    shadow=Image.new('RGBA',(raw.width+40,raw.height+40))
    a=raw.getchannel('A').point(lambda n:round(n*.24))
    sh=Image.new('RGBA',raw.size,(30,25,45,0));sh.putalpha(a)
    shadow.alpha_composite(sh,(24,29));shadow=shadow.filter(ImageFilter.GaussianBlur(7))
    shadow.alpha_composite(raw,(20,20));return shadow

def sprite(im,asset,x,y,size=360,t=0,pose=None,angle=0,active=True):
    definition=MANIFEST['stickers'][asset]
    if pose is None:
        poses=list(definition['sprites'])
        pose=poses[1+int(t*3)%3] if active else poses[0]
    # Quantized transform cache affects artwork only, not positional smoothness.
    size=max(32,round(size/8)*8);angle=round(angle/2)*2
    art=sticker_image(asset,pose,size,angle)
    im.alpha_composite(art,(round(x-art.width/2),round(y-art.height/2)))

def arrow(im,a,b,color=PINK,width=12):
    d=ImageDraw.Draw(im);d.line((a,b),fill=color,width=width)
    theta=math.atan2(b[1]-a[1],b[0]-a[0]);r=22
    d.polygon([b,(b[0]-r*math.cos(theta-.6),b[1]-r*math.sin(theta-.6)),(b[0]-r*math.cos(theta+.6),b[1]-r*math.sin(theta+.6))],fill=color)

def pointer(im,x,y,tap=False):
    d=ImageDraw.Draw(im)
    if tap:
        for r in [38,65]:d.ellipse((x-r,y-r,x+r,y+r),outline=PINK,width=5)
    d.polygon([(x,y),(x+4,y+55),(x+19,y+43),(x+31,y+67),(x+43,y+59),(x+29,y+36),(x+50,y+33)],fill='white',outline=INK,width=4)

def book(im,world,t):
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((60,189,1864,884),28,fill='#cabda8')
    d.rounded_rectangle((56,174,1864,866),28,fill='white')
    im.alpha_composite(background(world),(64,182))
    d.line((960,190,960,848),fill='#ffffff44',width=2)
    pill(im,MANIFEST['pages'][world]['name'].upper(),170,875,color=GREEN,size=23)

def trail(im,points,color=PINK):
    d=ImageDraw.Draw(im)
    if len(points)>1:d.line([(round(x),round(y)) for x,y in points],fill=color,width=8,joint='curve')
    for x,y in points[::3]:d.ellipse((x-5,y-5,x+5,y+5),fill=YELLOW)

def confetti(im,t,strength=1):
    d=ImageDraw.Draw(im)
    for i in range(round(45*strength)):
        x=(i*173+91)%W;y=(i*137+t*(48+i%8*8))%H
        if 180<y<870:continue
        color=[PINK,BLUE,YELLOW,GREEN][i%4]
        d.rounded_rectangle((x,y,x+11,y+22),3,fill=color)

def world_grid(im,t,focus=None):
    d=ImageDraw.Draw(im)
    for i,world in enumerate(PAGES):
        x=85+(i%3)*595;y=210+(i//3)*335
        d.rounded_rectangle((x-7,y-7,x+567,y+292),22,fill='white')
        im.alpha_composite(background(world,560,245),(x,y))
        text(im,MANIFEST['pages'][world]['name'],x+280,y+270,30)
        asset=['frog','fish','puppy','robot','astronaut','david-orban'][i]
        sprite(im,asset,x+430,y+160,160,t+i,angle=math.sin(t+i)*5)
        if focus==i:d.rounded_rectangle((x-9,y-9,x+569,y+294),23,outline=PINK,width=7)

def pipeline(im,t,compress=False,live_language=False):
    d=ImageDraw.Draw(im)
    labels=['CHILD','OMEGA LLM','OMEGA JEV','HOST KERNEL','STICKER']
    xs=[230,590,960,1330,1690]
    for i,(label,x) in enumerate(zip(labels,xs)):
        d.rounded_rectangle((x-135,385,x+135,650),30,fill='white',outline=[PINK,BLUE,PINK,GREEN,YELLOW][i],width=6)
        text(im,label,x,675,28)
        if i<4:arrow(im,(x+145,520),(xs[i+1]-145,520),color=[PINK,BLUE,PINK,GREEN][i])
    text(im,'"Flutter!"' if live_language else '"Make it fly"',xs[0],505,32,width=250)
    if compress:
        for j in range(5):d.rounded_rectangle((470,440+j*30,710-j*20,455+j*30),7,fill='#d7e2ff')
    else:text(im,'meaning',xs[1],510,37,BLUE)
    logo=Image.open(HERE/'input/jev.png').convert('RGBA').resize((130,130),Image.Resampling.LANCZOS)
    im.alpha_composite(logo,(xs[2]-65,425))
    text(im,'offered key',xs[2],600,23)
    text(im,'ADMITTED' if live_language else 'ACCEPT',xs[3],495,40,GREEN)
    text(im,'bounded goal' if live_language else 'or REFUSE',xs[3],550,29)
    sprite(im,'butterfly' if live_language else 'bird',xs[4],515,230,t)
    if live_language:text(im,'activity started',xs[4],625,22)
    p=(t*.7)%4;i=int(p);x=lerp(xs[i],xs[i+1],p-i)
    d.ellipse((x-12,708,x+12,732),fill=PINK)
    text(im,'The host owns the choices. The kernel owns every mutation.',960,790,34)

@lru_cache(maxsize=1)
def docker_logo():
    return Image.open(BytesIO(cairosvg.svg2png(url=str(HERE/'input/Docker-svgrepo-com.svg'),output_width=90,output_height=90))).convert('RGBA')

def receipt_points():
    p=PROOF['proofs'][0];events=p['audit']['events']
    out=[(0,.38,.45,3)]
    start=events[0]['at']
    for e in events:
        if e['kind']=='receipt' and e['receipt']['action']=='move-sticker' and e['receipt']['accepted']:
            out.append((e['at']-start,e['position']['x'],e['position']['y'],e['receipt']['resultRevision']))
    return out

POINTS=receipt_points()

def proof_motion(im,p,child=False):
    # Every positional endpoint comes from an actual accepted receipt. Tweening
    # merely makes the evidence legible and submits no world mutations.
    elapsed=lerp(0,POINTS[-1][0],ease(p))
    idx=max(0,bisect.bisect_right([r[0] for r in POINTS],elapsed)-1)
    prev=POINTS[idx];nxt=POINTS[min(idx+1,len(POINTS)-1)]
    a=0 if nxt[0]==prev[0] else clamp((elapsed-prev[0])/(nxt[0]-prev[0]))
    x=lerp(prev[1],nxt[1],a);y=lerp(prev[2],nxt[2],a)
    if child:x=lerp(POINTS[-1][1],.68,ease(p));y=lerp(POINTS[-1][2],.52,ease(p))
    path=[(64+r[1]*1792,182+r[2]*670) for r in POINTS[:idx+1]]
    trail(im,path,BLUE)
    sx,sy=64+x*1792,182+y*670
    sprite(im,'butterfly',sx,sy,340,p*5)
    pointer(im,sx+35,sy+10,tap=not child and p<.24)
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((1150,275,1770,630),25,fill='#fffffff2',outline=GREEN,width=4)
    text(im,'REAL RUNTIME TRACE',1460,325,32,GREEN)
    human=next(x for x in PROOF['proofs'] if x['id']=='human-hand')['move']['receipt']
    details=['child grab → host revokes play','actor: human:kid','selectedBy: null',f"kernel accepted revision {human['resultRevision']}"] if child else ['child double-tap → Jev','translatedBy: null','selectedBy: agent:jev-visual-1',f'kernel accepted revision {prev[3]}']
    for j,line in enumerate(details):
        text(im,line,1460,390+j*46,25,width=570,mono=True)
    if child:pill(im,'CHILD GRAB → AUTONOMY STOPPED',960,775,GREEN,32)
    else:pill(im,'ACCEPTED POSITIONS / TIME COMPRESSED',960,775,BLUE,29)

def isolation(im,p):
    d=ImageDraw.Draw(im)
    for world,x in [('farm',90),('space',1000)]:
        im.alpha_composite(background(world,820,410),(x,300))
        d.rounded_rectangle((x-5,295,x+825,715),25,outline='white',width=8)
        text(im,world.upper(),x+410,260,42)
    sprite(im,'butterfly',540,525,290,p*5)
    text(im,'NO FARM STICKER',1410,505,36,'white')
    arrow(im,(750,740),(1210,740),PINK)
    d.line((950,695,990,780),fill=INK,width=12);d.line((990,695,950,780),fill=INK,width=12)
    pill(im,'FARM STICKER ABSENT IN SPACE',960,810,BLUE,31)
    text(im,'REAL HOST WORLD STATE / reconstructed from captured page responses',960,865,25)

def render(t):
    shot=TIMELINE[max(0,bisect.bisect_right(STARTS,t)-1)]
    cut_dt=max(0,t-shot['start'])
    dt=max(0,t-shot.get('visual_start',shot['start']));p=clamp(dt/max(.1,shot.get('visual_end',shot['end'])-shot.get('visual_start',shot['start'])))
    im=Image.new('RGBA',(W,H),PAPER);d=ImageDraw.Draw(im)
    # Deterministic soft paper dots, never unrelated stock or generated video.
    for y in range(25,H,42):
        for x in range(24,W,42):d.ellipse((x,y,x+2,y+2),fill='#e9ddc9')
    scene=shot['scene'];world=shot['world'];title=shot['title'];subject=shot['subject']
    beat=max(0,bisect.bisect_right(AUDIO['beats'],t)-1)
    pulse=math.exp(-max(0,t-AUDIO['beats'][beat])*8)
    if scene not in {'worlds','cover','pipeline','proof-language','compress','choices','isolation','outro','shell'}:book(im,world,t)
    if scene=='cover':
        src=ROOT/'web'/MANIFEST['cover']['variants']['landscape']['src']
        cover=cover_image()
        scale=.87+.07*ease(p)
        if p>.6:world_grid(im,t)
        fold=1-.95*ease((p-.6)/.4)
        art=cover.resize((max(30,round(cover.width*scale*fold)),round(cover.height*scale)),Image.Resampling.LANCZOS)
        im.alpha_composite(art,((W-art.width)//2,220))
        sprite(im,'frog',1580,760,260,t);sprite(im,'bird',340,350,230,t)
    elif scene=='worlds':world_grid(im,t,beat%6);confetti(im,t,.6)
    elif scene=='tray':
        for i,asset in enumerate(['frog','bird','butterfly','fish','cloud','flower','cow','robot']):
            x=240+i%4*480;y=370+i//4*300
            d.rounded_rectangle((x-200,y-130,x+200,y+140),25,fill='white',outline='#ead8ba',width=3)
            sprite(im,asset,x,y,270,t+i,active=False)
        pointer(im,300,420,tap=True)
    elif scene in {'hop','chorus','play','boundary','cameo','ensemble'}:
        if scene=='ensemble':
            for i,asset in enumerate(['frog','bird','butterfly','fish','robot','flower']):
                sprite(im,asset,250+i*280,570+70*math.sin(t*3+i),310,t+i,angle=math.sin(t*2+i)*8)
        elif scene=='cameo' and shot['cameo']:
            sprite(im,shot['cameo'],960,520,560,t,angle=math.sin(t*2)*4)
            for i,asset in enumerate(['butterfly','fish','frog']):sprite(im,asset,400+i*570,760,180,t+i)
        else:
            hop=max(0,math.sin((t-AUDIO['phase'])*math.pi/(60/AUDIO['bpm'])))
            x=960+180*math.sin(t*.9);y=665-250*hop
            sprite(im,'frog',x,y,440+32*pulse,t,pose='hop' if hop>.35 else 'land',angle=math.sin(t)*5)
            sprite(im,'bird',360+90*math.sin(t),350+65*math.sin(t*2),250,t)
            sprite(im,'butterfly',1550+100*math.cos(t),430+100*math.sin(t*.8),280,t)
            if scene=='boundary':d.rounded_rectangle((170,260,1750,795),40,outline=PINK,width=7)
        if scene=='chorus':confetti(im,t)
    elif scene in {'flight','accelerate'}:
        x=lerp(360,1550,ease(p));y=660-280*math.sin(math.pi*p)
        trail(im,[(lerp(360,1550,q),660-280*math.sin(math.pi*q)) for q in [max(0,p-j*.04) for j in range(12)][::-1]],BLUE)
        sprite(im,subject,x,y,440,t,angle=-15*math.cos(p*math.pi))
        if shot['cameo']:sprite(im,shot['cameo'],300,700,260,t)
    elif scene=='drag':
        x=lerp(370,1300,ease(p));y=lerp(340,590,ease(p))
        sprite(im,subject,x,y,420,t,active=False);pointer(im,x+80,y+80)
        if p>.75:pill(im,'PLACED',1300,790,GREEN)
    elif scene=='curve':
        sprite(im,'ray-kurzweil',430,550,470,t)
        pts=[(780+900*q,740-550*q*q) for q in [j/60 for j in range(round(60*ease(p))+1)]]
        trail(im,pts,PINK)
        if pts:arrow(im,pts[-2] if len(pts)>1 else pts[0],(pts[-1][0]+40,pts[-1][1]-60),PINK)
        text(im,'tomorrow',1450,780,48)
    elif scene=='repair':
        if shot['cameo']:sprite(im,shot['cameo'],420,560,480,t)
        sprite(im,'frog',1120,570,430,t)
        for i in range(14):
            if i/14>p:d.line((730+i*58,240,770+i*58,790),fill='#a69676',width=3)
        d.rounded_rectangle((720,260,1650,790),28,outline=GREEN,width=7)
        pill(im,'BOUNDARY INTACT',1200,775,GREEN)
    elif scene=='sense':
        sprite(im,'david-eagleman',480,550,470,t)
        sprite(im,'butterfly',1250,530,400,t)
        for i in range(5):
            r=60+((t*120+i*70)%360);d.ellipse((1250-r,530-r,1250+r,530+r),outline=[PINK,BLUE,YELLOW][i%3],width=5)
        pill(im,'A NEW WAY TO SENSE',960,805,BLUE)
    elif scene=='meters':
        sprite(im,'frog',560,600-80*pulse,440,t)
        for label,x,color,up in [('P-HOP',1120,GREEN,True),('P-DOOM',1510,PINK,False)]:
            d.rounded_rectangle((x-110,330,x+110,760),70,fill='white',outline=color,width=5)
            height=lerp(100,330,ease(p)) if up else lerp(330,100,ease(p))
            d.rounded_rectangle((x-86,735-height,x+86,735),60,fill=color)
            text(im,label,x,810,45,color)
            arrow(im,(x,650),(x,395 if up else 710),YELLOW,10)
    elif scene in {'pipeline','proof-language','compress'}:
        pipeline(im,dt,scene=='compress',scene=='proof-language')
        if scene=='proof-language':
            d.rounded_rectangle((235,740,1685,905),25,fill='white',outline=GREEN,width=4)
            language=next(x for x in PROOF['proofs'] if x['id']=='language')
            text(im,f"ACTUAL OMEGALLM TURN / {language['elapsed']:.2f}s / time compressed",960,773,29,GREEN)
            text(im,'"Make the butterfly flutter."',960,822,34)
            text(im,'bounded goal: butterfly-1 / animate / flutter',960,870,28,BLUE,mono=True)
    elif scene=='choices':
        for i,(label,color) in enumerate([('MOVE',BLUE),('FACE',PINK),('ANIMATE',GREEN),('NOOP',INK)]):
            x=285+i*450;d.rounded_rectangle((x-190,360,x+190,700),30,fill='white',outline=color,width=6)
            text(im,label,x,480,52,color)
            sprite(im,'frog',x,600,190,t,active=i==2)
            if i==beat%4:d.rounded_rectangle((x-200,350,x+200,710),34,outline=YELLOW,width=10)
        text(im,'Only CURRENT offered keys can be chosen',960,815,38)
    elif scene=='proof-double':proof_motion(im,p)
    elif scene=='proof-human':proof_motion(im,p,True)
    elif scene=='teach':
        positions=[.32,.38,.44,.50]
        for i,x in enumerate(positions):
            sx=64+x*1792;d.ellipse((sx-14,630,sx+14,658),fill=PINK)
            if i<3:arrow(im,(sx+20,645),(64+positions[i+1]*1792-20,645),BLUE,7)
        x=lerp(positions[0],positions[-1],ease(p))
        sprite(im,'frog',64+x*1792,555,350,t)
        pill(im,'child teaches → host remembers → Jev can recall',960,785,BLUE,30)
        text(im,'Illustrated pattern / each replayed action still needs a receipt',960,840,24)
    elif scene=='memory':
        for i,label in enumerate(['accepted history','remembered pattern','bounded suggestion']):
            x=420+i*540;d.rounded_rectangle((x-200,380,x+200,660),25,fill='white',outline=BLUE,width=4)
            text(im,label,x,430,31,width=370)
            sprite(im,'frog',x,555,230,t+i)
            if i<2:arrow(im,(x+212,520),(x+328,520),PINK)
        text(im,'Advisory memory does not add legal actions',960,795,37)
    elif scene=='isolation':isolation(im,p)
    elif scene in {'shell','localhost'}:
        if shot['cameo']:sprite(im,shot['cameo'],350,550,420,t)
        x=1100 if shot['cameo'] else 960
        d.rounded_rectangle((x-370,320,x+370,770),40,fill='white',outline=BLUE,width=8)
        text(im,'HOST KERNEL',x,365,42,GREEN)
        for j,label in enumerate(['OmegaLLM','OmegaJev']):
            bx=x-175+j*350;d.rounded_rectangle((bx-140,425,bx+140,680),28,fill='#eef4ff',outline=PINK,width=4)
            text(im,label,bx,490,34)
            text(im,'localhost',bx,550,24,mono=True)
            text(im,':8761' if j==0 else ':8762',bx,600,28,BLUE,mono=True)
        sprite(im,'frog',x+420,740,240,t)
        text(im,'Host coordinates. Agents do not mutate the world.',960,825,34)
        pill(im,'LOCAL DEV: DOCKER ≠ OPENSHELL',960,905,INK,29)
        im.alpha_composite(docker_logo(),(x-45,685))
    elif scene=='outro':
        world_grid(im,t)
        if title=='HOP!':
            d.rectangle((0,0,W,H),fill=PINK);text(im,'HOP!',960,475,280,'white')
            sprite(im,'frog',960,800-180*math.sin(p*math.pi),440,t,pose='hop')
        else:pill(im,'LITTLE MOVES. VISIBLE RULES.',960,940,GREEN,34)
    if title and scene!='outro':
        size=round(96+14*pulse) if title in {'P-HOP','MAKE THE FROG HOP','MAKE THE BIRD FLY'} else 68
        text(im,title,960,95,size,PINK if 'HOP' in title else INK,width=1770)
    # Minimal editorial lyric cue, sourced ONLY from the supplied lyric file.
    # Unmatched tail ideas are staged visually; do not pretend they are karaoke.
    if scene!='outro' and shot['confidence']>=.45:
        text(im,shot['lyric'],960,979,37,INK,width=1740)
    text(im,'StickerBook',91,1035,25,GREEN,anchor='lm')
    text(im,'I\'M UPPING MY P(HOP)',1815,1035,22,INK,anchor='rm')
    # Tiny bounded page-turn flourish at cuts, no long crossfade muddying art.
    if 0<cut_dt<.22 and scene not in {'cover','outro'}:
        width=round((1-ease(cut_dt/.22))*W*.22)
        if width:d.polygon([(W-width,0),(W,0),(W,H),(W-width*.7,H)],fill='#fff3db',outline='#d8c8a9')
    return im.convert('RGB')

@lru_cache(maxsize=1)
def cover_image():
    src=ROOT/'web'/MANIFEST['cover']['variants']['landscape']['src']
    return Image.open(BytesIO(cairosvg.svg2png(url=str(src),output_width=1650))).convert('RGBA')

def render_rgb(t):
    return render(t).tobytes()

def frame_bytes(times,workers):
    if workers==1:
        for t in times:yield render_rgb(t)
        return
    # Keep at most eight raw frames queued (~48 MiB); never accumulate an
    # entire video's uncompressed RGB buffers or spawn model processes.
    with ProcessPoolExecutor(max_workers=workers) as pool:
        pending=deque();iterator=iter(times)
        for _ in range(8):
            t=next(iterator,None)
            if t is not None:pending.append(pool.submit(render_rgb,t))
        while pending:
            yield pending.popleft().result()
            t=next(iterator,None)
            if t is not None:pending.append(pool.submit(render_rgb,t))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=HERE/'output/stickerbook-phop.mp4')
    parser.add_argument('--from',dest='start',type=float,default=0)
    parser.add_argument('--to',type=float,default=AUDIO['duration'])
    parser.add_argument('--stills',action='store_true')
    parser.add_argument('--workers',type=int,choices=[1,2],default=1)
    args=parser.parse_args();args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.stills:
        times=[.8,3.5,4.9,6,12.8,16,20.7,23,30,47.6,52.8,55.5,62.1,64.8,76.5,81,85.5,92.8,96.8,102.7,113,127.5,134,138,145.2,152.4,158.8,166.9,173,179.65]
        sheet=Image.new('RGB',(5*384,6*238),PAPER)
        for i,t in enumerate(times):
            frame=render(t);frame.save(HERE/f'output/still-{t:06.2f}.png')
            thumb=frame.resize((384,216),Image.Resampling.LANCZOS);sheet.paste(thumb,(i%5*384,i//5*238))
            ImageDraw.Draw(sheet).text((i%5*384+7,i//5*238+218),f'{t:.2f}s',fill=INK)
        sheet.save(HERE/'output/contact-sheet.png');print('Saved 30 shot stills and contact sheet');return
    duration=min(args.to,AUDIO['duration'])-args.start
    assert duration>0 and args.start>=0, 'Invalid master-clock window'
    temporary=args.output.with_name(args.output.stem+'.rendering.mp4')
    # 179.84 is not an integer number of 30-fps frames. 5396 frames cover it;
    # -t clips final sample duration to the absolute audio clock, no added fade.
    frames=math.ceil(duration*30)
    cmd=['ffmpeg','-y','-hide_banner','-loglevel','warning','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{W}x{H}','-framerate','30','-i','pipe:0',
         '-ss',str(args.start),'-i',str(ROOT/'assets/video/audio/im-upping-my-phop.wav'),'-map','0:v','-map','1:a',
         '-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','320k','-t',f'{duration:.6f}',
         '-video_track_timescale','90000','-movflags','+faststart',str(temporary)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE);start=time.monotonic()
    try:
        for i,raw in enumerate(frame_bytes((args.start+j/30 for j in range(frames)),args.workers)):
            proc.stdin.write(raw)
            if i%300==0:print(f'{i}/{frames} frames; {time.monotonic()-start:.1f}s render',flush=True)
    except BaseException:
        proc.stdin.close();proc.wait();raise
    finally:
        if not proc.stdin.closed:proc.stdin.close()
    assert proc.wait()==0,'FFmpeg export failed'
    from exact_clock import fix
    fix(temporary,duration)
    temporary.replace(args.output)
    print('Exported',args.output,flush=True)

if __name__=='__main__':main()
