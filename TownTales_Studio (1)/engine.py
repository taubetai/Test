"""Local orchestration. No cloud APIs. Run with the existing MLX virtualenv."""
import os,json,uuid,threading,subprocess,sys,re,urllib.request,shutil,math
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
ROOT=Path(__file__).resolve().parent; OUT=ROOT/'jobs'; OUT.mkdir(exist_ok=True)
VOICE_ROOT=Path(os.getenv('TOWNTALES_VOICE_ROOT',str(Path.home()/'TownTalesStudio'/'narrators')))
REF_TEXT='In this town, there was one rule that everyone had to follow. You could never open your front door after midnight. Now, most people thought this was completely normal. But one kid wanted to find out why. So, he opened the door. And what he saw on the other side made him instantly regret it.'
MODEL=os.getenv('TOWNTALES_LLM','qwen2.5:7b'); TTS='mlx-community/Qwen3-TTS-12Hz-1.7B-Base-5bit'; BLENDER=os.getenv('BLENDER','/Applications/Blender.app/Contents/MacOS/Blender'); FFMPEG=os.getenv('FFMPEG','ffmpeg'); JOBS={}; LOCK=threading.Lock()
def run(args):
 p=subprocess.run([str(x) for x in args],capture_output=True,text=True); 
 if p.returncode: raise RuntimeError((p.stderr or p.stdout)[-4000:])
 return p.stdout
def ollama(prompt):
 data=json.dumps({'model':MODEL,'prompt':prompt,'stream':False,'format':'json','options':{'temperature':0.8,'num_ctx':8192}}).encode(); req=urllib.request.Request('http://127.0.0.1:11434/api/generate',data,{'Content-Type':'application/json'}); return json.loads(json.load(urllib.request.urlopen(req,timeout=600))['response'])
def update(j,**kwargs): JOBS[j].update(kwargs)
def ass_time(t):
 n=max(0,round(t*100)); return f'{n//360000}:{n//6000%60:02}:{n//100%60:02}.{n%100:02}'
def probe(p): return float(run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',p]).strip())
def make_plan(prompt,duration,previous,edit):
 n=round(duration/3); w=round(duration*2.65)
 instruction=f'''Write a gripping original mystery short inspired by this premise: {prompt!r}. The exact opening words MUST be In this town. Target {w} words total, approximately {n} shots. Build a specific rule, character goal, consequential actions, escalating danger, surprising but logically earned twist and ending. Avoid repetitive exposition. Every shot must visibly depict its narration, change composition or action, and use purposeful props. Return JSON object {{"title":"...","shots":[{{"narration":"...","location":"street|bedroom|forest|hallway|classroom|shop|basement","time":"day|night|red","action":"walk|run|look|reach|shock|hide|turn|idle","camera":"wide|close|low|overhead|tracking","character":"main|stranger|both","props":[{{"kind":"door|mirror|letter|clock|tree|lamp|book|box|window|sign|table|chair|phone|key|custom","name":"specific short noun","color":"#RRGGBB","x":1,"y":2,"z":0,"size":1}}]}}]}}. Each narration 5-15 words; use the same protagonist and antagonist across shots. Props coordinates x -3 to 3, y -2 to 4, z 0 to 2, size .3 to 2. Use only supported enum values. No dialogue tags. JSON only.'''
 if previous: instruction+=f'\nPrevious film: {json.dumps(previous)}\nRevision: {edit}. Preserve unaffected story elements.'
 for _ in range(3):
  p=ollama(instruction); shots=p.get('shots',[]); text=' '.join(str(s.get('narration','')) for s in shots); 
  if len(shots)>=max(3,n//2) and len(shots)<=n*2 and text.lower().startswith('in this town') and w*.65<=len(text.split())<=w*1.4 and all(isinstance(s.get('props',[]),list) and s.get('narration') for s in shots): return p
  instruction+='\nYour last result failed shot count, opening, or word count. Correct it.'
 raise RuntimeError('Story planner did not produce a valid duration-sized plan. Try another prompt.')
def pipeline(j,body):
 with LOCK:
  try:
   import wave
   import numpy as np
   import mlx_whisper
   d=OUT/j; d.mkdir(); duration=int(body['duration']); previous=None
   if body.get('parent') and body.get('edit'):
    parent=str(uuid.UUID(body['parent'])); previous=json.loads((OUT/parent/'plan.json').read_text())
   update(j,progress=5,message='Writing original story and directing scenes…'); plan=make_plan(body['prompt'],duration,previous,body.get('edit','')); shots=plan['shots']; (d/'plan.json').write_text(json.dumps(plan,indent=2)); update(j,story='\n'.join(s['narration'] for s in shots))
   ref=next(iter(sorted(VOICE_ROOT.glob('voice_J.wav'))+sorted(VOICE_ROOT.glob('voice_J_*.wav'))),None)
   if not ref: raise RuntimeError(f'Voice J WAV not found in {VOICE_ROOT}')
   # One speech generation for story continuity; align with local Whisper.
   text=' '.join(s['narration'].strip() for s in shots); update(j,progress=12,message='Generating Voice J narration…')
   run([sys.executable,'-m','mlx_audio.tts.generate','--model',TTS,'--ref_audio',ref,'--ref_text',REF_TEXT,'--text',text,'--max_tokens','8192','--output_path',d,'--file_prefix','narration','--audio_format','wav','--join_audio'])
   raw=next(d.glob('narration*.wav')); slow=d/'slow.wav'; run([FFMPEG,'-y','-i',raw,'-af','atempo=0.90','-ar','24000','-ac','1',slow]); update(j,progress=22,message='Aligning speech and subtitles locally…')
   tr=mlx_whisper.transcribe(str(slow),path_or_hf_repo='mlx-community/whisper-small-mlx',word_timestamps=True,language='en'); words=[w for s in tr['segments'] for w in s.get('words',[])];
   if not words: raise RuntimeError('No speech timestamps found')
   # Map transcript words to script tokens; reject obvious omissions rather than export cut-off narration.
   import difflib
   norm=lambda s:re.sub(r'[^a-z0-9]','',s.lower()); tokens=text.split(); a=[norm(x) for x in tokens]; b=[norm(w['word']) for w in words]; matches={}
   for block in difflib.SequenceMatcher(None,a,b,autojunk=False).get_matching_blocks():
    for i in range(block.size): matches[block.a+i]=block.b+i
   if len(matches)<.85*len(tokens) or len(tokens)-1 not in matches: raise RuntimeError('Narration incomplete or alignment unreliable; regenerate instead of exporting clipped speech.')
   with wave.open(str(slow),'rb') as f: rate=f.getframerate(); pcm=np.frombuffer(f.readframes(f.getnframes()),dtype=np.int16).copy()
   # Add only missing gap duration, no speech removed. Do not insert inside overlapping boundaries.
   inserts=[]
   for i,t in enumerate(tokens[:-1]):
    if i not in matches or i+1 not in matches: continue
    target=.45 if t.endswith(('...','…')) else .30 if t.endswith(('.','!','?')) else .125 if t.endswith(',') else 0
    if not target: continue
    left=float(words[matches[i]]['end']); right=float(words[matches[i+1]]['start']); gap=right-left
    if gap>=.025 and gap<target:
     at=int((left+right)/2*rate); window=pcm[max(0,at-int(.012*rate)):at+int(.012*rate)].astype(float)
     if len(window) and np.sqrt(np.mean(window**2))<900: inserts.append((at,int((target-gap)*rate)))
   parts=[]; last=0
   for at,count in sorted(inserts): parts.extend([pcm[last:at],np.zeros(count,dtype=np.int16)]); last=at
   parts.append(pcm[last:]); adjusted=np.concatenate(parts); audio=d/'timed.wav'
   with wave.open(str(audio),'wb') as f: f.setnchannels(1); f.setsampwidth(2); f.setframerate(rate); f.writeframes(adjusted.tobytes())
   def shift(t): return t+sum(c/rate for at,c in inserts if at/rate<=t)
   actual=len(adjusted)/rate; factor=actual/duration
   if not .75<=factor<=1.35: raise RuntimeError(f'Story audio {actual:.1f}s is too far from requested {duration}s. Regenerate.')
   finalaudio=d/'voice.wav'; run([FFMPEG,'-y','-i',audio,'-af',f'atempo={factor:.6f},apad','-t',str(duration),finalaudio]);
   # Scale alignment to the final tempo. Word events are individually highlighted.
   for w in words: w['start']=shift(float(w['start']))/factor; w['end']=shift(float(w['end']))/factor
   ass=d/'captions.ass'; width,height=(1080,1920) if body['quality']=='full' else (540,960); fs=round(width*.066)
   header=f'''[Script Info]\nScriptType: v4.00+\nPlayResX: {width}\nPlayResY: {height}\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Arial,{fs},&H0000FFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,{max(2,width//180)},1,2,35,35,{round(height*.22)},1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'''
   events=[]
   for i,w in enumerate(words):
    start=w['start']; end=min(duration,words[i+1]['start'] if i+1<len(words) else w['end']); word=re.sub(r'[{}\\\n]','',w['word'].strip()).upper()
    if end>start: events.append(f'Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{{\\fscx108\\fscy108\\t(0,100,\\fscx100\\fscy100)}}{word}')
   ass.write_text(header+'\n'.join(events)); boundaries=[0]; pos=0
   for s in shots[:-1]:
    pos+=len(s['narration'].split()); nearby=next((matches[k] for k in range(pos,min(pos+5,len(tokens))) if k in matches),None); t=words[nearby]['start'] if nearby is not None else duration*pos/len(tokens); boundaries.append(min(duration,max(boundaries[-1]+.15,t)))
   boundaries.append(duration); clips=[]
   for i,s in enumerate(shots):
    sec=boundaries[i+1]-boundaries[i];
    if sec<=0: continue
    update(j,progress=30+int(60*i/len(shots)),message=f'Rendering new shot {i+1}/{len(shots)}…'); spec=d/f'shot{i}.json'; spec.write_text(json.dumps({'shot':s,'duration':sec,'width':width,'height':height,'seed':int(uuid.UUID(j))%100000+i})); clip=d/f'shot{i}.mp4'; run([BLENDER,'-b','-t','4','--python',ROOT/'render.py','--',spec,clip]); clips.append(clip)
   concat=d/'concat.txt'; concat.write_text(''.join(f"file '{p.name}'\n" for p in clips)); update(j,progress=94,message='Editing and burning in captions…'); final=d/'film.mp4'
   # Run filter from a controlled absolute path; use relative subtitle file to avoid escaping.
   p=subprocess.run([FFMPEG,'-y','-f','concat','-safe','0','-i','concat.txt','-i','voice.wav','-vf','ass=captions.ass','-map','0:v','-map','1:a','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-t',str(duration),'-movflags','+faststart','film.mp4'],cwd=d,capture_output=True,text=True)
   if p.returncode: raise RuntimeError(p.stderr[-3000:])
   update(j,state='done',progress=100,message=f'Finished • {probe(final):.1f} seconds',video=f'/jobs/{j}/film.mp4',subtitles=f'/jobs/{j}/captions.ass',plan=f'/jobs/{j}/plan.json')
  except Exception as e: update(j,state='error',message='Generation stopped',error=str(e))
class Handler(BaseHTTPRequestHandler):
 def cors(self):
  origin=self.headers.get('Origin',''); allowed=os.getenv('TOWNTALES_PAGES_ORIGIN','');
  if origin in ('http://127.0.0.1:8765','http://localhost:8765',allowed) and origin: self.send_header('Access-Control-Allow-Origin',origin); self.send_header('Vary','Origin'); self.send_header('Access-Control-Allow-Private-Network','true')
  self.send_header('Access-Control-Allow-Headers','Content-Type'); self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS')
 def reply(self,data,status=200):
  b=json.dumps(data).encode(); self.send_response(status); self.cors(); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
 def do_OPTIONS(self): self.send_response(204); self.cors(); self.end_headers()
 def do_POST(self):
  if self.path!='/jobs': return self.reply({'error':'Not found'},404)
  origin=self.headers.get('Origin','');
  if origin and origin not in ('http://127.0.0.1:8765','http://localhost:8765',os.getenv('TOWNTALES_PAGES_ORIGIN','')): return self.reply({'error':'Origin not allowed'},403)
  try:
   b=json.loads(self.rfile.read(min(int(self.headers['Content-Length']),20000))); assert 15<=int(b['duration'])<=120 and b['quality'] in ('full','preview') and 0<len(b['prompt'])<4000; j=str(uuid.uuid4()); JOBS[j]={'state':'running','progress':0,'message':'Queued'}; threading.Thread(target=pipeline,args=(j,b),daemon=True).start(); self.reply({'id':j},202)
  except Exception: self.reply({'error':'Invalid request'},400)
 def do_GET(self):
  import mimetypes
  if self.path=='/health': return self.reply({'message':'Local engine connected. Generation requires Ollama, Blender, FFmpeg and Voice J.'})
  parts=self.path.strip('/').split('/')
  if len(parts)==2 and parts[0]=='jobs': return self.reply(JOBS.get(parts[1],{'error':'Unknown job'}),200 if parts[1] in JOBS else 404)
  if self.path in ('/','/index.html','/README.md'): p=ROOT/('README.md' if self.path=='/README.md' else 'index.html')
  elif len(parts)==3 and parts[0]=='jobs' and parts[2] in ('film.mp4','captions.ass','plan.json'):
   try: p=OUT/str(uuid.UUID(parts[1]))/parts[2]
   except ValueError: return self.reply({'error':'Not found'},404)
  else: return self.reply({'error':'Not found'},404)
  if not p.exists(): return self.reply({'error':'Not found'},404)
  self.send_response(200); self.cors(); self.send_header('Content-Type',mimetypes.guess_type(p)[0] or 'application/octet-stream'); self.send_header('Content-Length',str(p.stat().st_size)); self.end_headers();
  with p.open('rb') as f: shutil.copyfileobj(f,self.wfile)
if __name__=='__main__': print('TownTales Studio: http://127.0.0.1:8765',flush=True); ThreadingHTTPServer(('127.0.0.1',8765),Handler).serve_forever()
