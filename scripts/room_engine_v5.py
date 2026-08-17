#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,os,random,re
from datetime import datetime,timezone
from pathlib import Path
from room_private_model import run as model_run
from room_social_v5 import ORDER,audit_invariants,choose_partner,migrate_minds,migrate_state,new_topic_from_terms,observe_message,plan_actions,should_shift_topic,topic_terms_from_messages,update_topic

ROOT=Path(__file__).resolve().parents[1]; ROOM=ROOT/'room'; PARTS=ROOT/'room_parts'; WORK=ROOT/'room_work'
CFG=json.loads((ROOM/'config.json').read_text()); A=CFG['a']; P=CFG['p']; BOOT=CFG.get('boot_id','room-default'); VERSION='room-cognition-v5'; N={e:P[e]['name'] for e in ORDER}
STOP=set('the and but for not was are you your our out too did can got one once that this with from have has had just what when where how there they them then than about would could should into only really some more very like because been being does doing done will well yeah okay also still maybe kind sort thing things something anything someone everyone say saying think thinking thought know knowing mean means seem seems want wants wanted make making made start starting started try trying tried good great nice sure right actually probably pretty little much many few around again already even ever never always often sometimes today tonight tomorrow yesterday different together interesting going everything current'.split())

def load(p,d): return json.loads(p.read_text()) if p.exists() else d
def save(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def rr(*x): return random.Random(int(hashlib.sha256(':'.join(map(str,x)).encode()).hexdigest()[:16],16)&0x7fffffff)
def clamp(x,a=0,b=1): return max(a,min(b,float(x)))
def toks(s):
 out=[]; names={v.lower() for v in N.values()}
 for w in re.findall(r"[a-z][a-z'-]{2,}",str(s or '').lower()):
  w=w.strip("'-"); w=w[:-2] if w.endswith("'s") else w
  if w and w not in STOP and w not in names and w not in out: out.append(w)
 return out

def fresh_minds():
 M={'entities':{}}
 for e in ORDER: M['entities'][e]={'fast':{'activation':.2,'attention':[]},'medium':{'topics':[],'branch_interest':0},'slow':{'social_energy':.55},'noise':{},'room_memories':[],'self_history':[],'last_event':None,'spoken':0,'silences':0,'people':{}}
 return migrate_minds(M)
def fresh_state(): return migrate_state({'version':VERSION,'boot_id':BOOT,'cycle':0,'messages':0,'beat_contributors':[]})
def init():
 ROOM.mkdir(exist_ok=True); st=load(ROOM/'state.json',{})
 if st.get('boot_id')!=BOOT:
  save(ROOM/'conversation.json',[]); save(ROOM/'discourse.json',{'nodes':[],'roots':[]}); save(ROOM/'cognitive_state.json',fresh_minds()); save(ROOM/'state.json',fresh_state()); return
 if not (ROOM/'conversation.json').exists(): save(ROOM/'conversation.json',[])
 if not (ROOM/'discourse.json').exists(): save(ROOM/'discourse.json',{'nodes':[],'roots':[]})
 if not (ROOM/'cognitive_state.json').exists(): save(ROOM/'cognitive_state.json',fresh_minds())
 if not (ROOM/'state.json').exists(): save(ROOM/'state.json',fresh_state())
init()
def conv(): return load(ROOM/'conversation.json',[])
def tree(): return load(ROOM/'discourse.json',{'nodes':[],'roots':[]})
def state(): return migrate_state(load(ROOM/'state.json',fresh_state()))
def minds(): return migrate_minds(load(ROOM/'cognitive_state.json',fresh_minds()))
def msgs(): return [m for m in conv() if str(m.get('runtime','')).startswith('room-cognition-v') and m.get('boot_id',BOOT)==BOOT]
def event(): return msgs()[-1] if msgs() else None
def trait(e,k,d=.5): return float(P[e]['traits'].get(k,d))
def ni(n): e=ORDER[n//3]; local=n%3; role,tasks=A['roles'][str(local)]; return e,local,role,tasks
def target(m): return ((m or {}).get('cognition') or {}).get('target')
def isq(m): return bool(m and str(m.get('text','')).rstrip().endswith('?'))

def sense(n,key):
 e,local,role,tasks=ni(n); C=msgs()[-8:]; last=C[-1] if C else None; M=minds(); S=state(); topic=S.get('topic_episode') or {}; partner=(last or {}).get('speaker')
 if partner not in ORDER or partner==e: partner=choose_partner(e,M,topic,int(S.get('cycle',0)))
 rel=M['entities'][e]['people'][partner]; base={'event':last,'context':C,'keywords':toks(' '.join(str(x.get('text','')) for x in C))[:16],'topic':{k:topic.get(k) for k in ('id','root','current_facet','facets','status')},'partner':partner,'relationship':{k:rel.get(k) for k in ('exposure','direct_familiarity','trust','predictability','reciprocity','warmth','respect','disclosure_depth','tension')}}
 model=model_run(role,{'entity':e,'profile':P[e],**base})
 if role=='comprehension': ready=.1; attention=clamp(.45+.35*trait(e,'social_sensitivity')); concepts=base['keywords'][:10]; field='social_observation'
 elif role=='thought': ready=.2; attention=clamp(.4+.35*trait(e,'curiosity')); concepts=[]; field='deliberation'
 else:
  ready=clamp(.38+.22*trait(e,'extraversion')+.25*trait(e,'curiosity')-.18*trait(e,'inhibition')+(.35 if last and target(last)==e else 0)); attention=.45; concepts=[]; field='expression'
 private={**base,field:model,'mandatory_speech':True}
 return {'phase':'sense','node':n,'entity':e,'local':local,'role':role,'tasks':tasks,'private':private,'public':{'node':n,'entity':e,'role':role,'attention':round(attention,3),'readiness':round(ready,3),'concepts':concepts}}

def bus(parts,key):
 if {p['node'] for p in parts}!=set(range(12)): raise RuntimeError('all 12 nodes required')
 concepts=[]
 for p in parts:
  for w in p['public'].get('concepts',[]):
   if w not in concepts: concepts.append(w)
 return {'key':key,'private':{e:[p for p in parts if p['entity']==e] for e in ORDER},'network':{'concepts':concepts[:20]}}
def recurrent(n,key,B):
 e,local,role,tasks=ni(n); src=next(p for p in B['private'][e] if p['role']==role); intent=None
 if role=='expression':
  ready=float(src['public'].get('readiness',.5)); intent={'readiness':ready,'latency':round(max(.05,1.35-.9*ready+.25*trait(e,'inhibition')+rr('latency',key,e).uniform(0,.12)),4),'mandatory_speech':True}
 return {'phase':'recurrent','node':n,'entity':e,'local':local,'role':role,'tasks':tasks,'private':{'source':src['private'],'intent':intent},'public':{'node':n,'entity':e,'role':role,'readiness':float(src['public'].get('readiness',0))}}
def order4(parts,prev,cycle):
 E={p['entity']:p for p in parts if p['role']=='expression' and p['private'].get('intent')}
 if set(E)!=set(ORDER): raise RuntimeError('four expression processes required')
 out=[e for _,_,e in sorted((p['private']['intent']['latency']-.2*p['private']['intent']['readiness']+.015*((ORDER.index(e)-cycle)%4),ORDER.index(e),e) for e,p in E.items())]
 d=target(prev) if prev else None
 if d in out: out.remove(d); out.insert(0,d)
 return out,E

STARTERS=[
 "What's a belief you changed because one concrete example wouldn't fit it?",
 "What's a place you remember mainly because of one small detail?",
 "What's a skill you respect more after trying it yourself?",
 "What's something people call simple that becomes complicated when you look closely?",
 "What's a routine you keep because it has actually earned your trust?",
 "What's a disagreement that taught you something useful?",
 "What's a sound, smell, or object that brings back a very specific memory?",
 "What's a rule you follow even though you can name a good exception to it?",
 "What's something you understand differently now than you did five years ago?",
 "What's a tiny behavior that changes how comfortable you feel around somebody?",
 "What's a problem you enjoy more once the obvious solution fails?",
 "What's a place you would return to for one particular reason rather than the whole experience?"
]
def _norm(text): return re.sub(r'\W+',' ',str(text or '').lower()).strip()
def _sim(a,b):
 a=_norm(a); b=_norm(b)
 if not a or not b:return 0.0
 if a==b:return 1.0
 A=set(a.split()); B=set(b.split()); return len(A&B)/max(1,len(A|B))
def recent_similarity(V,text,e=None,window=120):
 vals=[]
 for m in V[-window:]:
  if e and m.get('speaker')!=e: continue
  vals.append(_sim(text,m.get('text','')))
 return max(vals or [0.0])
def same(V,text): return recent_similarity(V,text)>=.92
def choose_novel(e,key,V,candidates):
 seen=[]
 for c in candidates:
  c=str(c or '').strip()
  if c and c not in seen: seen.append(c)
 if not seen:return ''
 scored=[]
 for c in seen:
  s=max(recent_similarity(V,c,e,140),.65*recent_similarity(V,c,None,60))
  scored.append((s,rr('novel',e,key,c).random(),c))
 scored.sort(key=lambda x:(x[0],x[1]))
 return scored[0][2]
def starter(e,V,key): return choose_novel(e,key,V,STARTERS)
def facet(topic,V): return (topic or {}).get('current_facet') or (topic_terms_from_messages(V[-12:]) or ['detail'])[0]
def detail_set(topic,V,e,key):
 raw=[]
 if topic:
  raw += [topic.get('current_facet'),topic.get('root')]
  raw += list(topic.get('recent_terms',[]))+list(topic.get('facets',[]))+list(topic.get('shared_references',[]))
 for m in V[-10:]: raw += toks(m.get('text',''))[:4]
 out=[]
 for x in raw:
  if x and x not in STOP and x not in out: out.append(x)
 if not out: out=['detail','example','exception']
 shift=rr('detail-order',e,key).randrange(len(out)) if out else 0
 return out[shift:]+out[:shift]
def stance_candidates(e,f,alt,third,tgt):
 who=N.get(tgt,tgt)
 if e=='sarah': return [
  f"The part of {f} I keep coming back to is how it changes when {alt} changes.",
  f"I don't think {f} stands alone; {alt} looks like the useful comparison.",
  f"I'd separate the pattern around {f} from the one-off case involving {third}.",
  f"What interests me in {f} is less the label than the point where {alt} stops predicting it."
 ]
 if e=='mara': return [
  f"For me, {f} gets concrete when it changes what happens between people, especially around {alt}.",
  f"I keep hearing {f} as a people question: who reacts differently when {alt} enters the picture?",
  f"The piece of {f} that feels real to me is the moment somebody responds differently because of {third}.",
  f"I'd rather pin {f} to an actual interaction than leave it as a general rule about {alt}."
 ]
 if e=='owen': return [
  f"I'd test {f} against {alt}; if it breaks there, that is a real exception rather than noise.",
  f"The useful distinction for me is {f} versus {alt}, because they should not be doing the same explanatory work.",
  f"I want a case where {f} predicts one thing and {third} predicts another; then we learn which rule survives.",
  f"Before I generalize {f}, I'd want to know what happens under the constraint imposed by {alt}."
 ]
 return [
  f"The weird edge of {f} is where {alt} points the other way; that's the version I want to look at.",
  f"I keep wanting to connect {f} with {third}, mostly because the connection is not obvious.",
  f"If {f} has a clean story, I want the messy case involving {alt} that ruins it a little.",
  f"The interesting version of {f} for me is the one where {alt} and {third} collide."
 ]
def question_candidates(e,f,alt,third,tgt):
 who=N.get(tgt,tgt)
 if e=='sarah': return [
  f"Can you pin {f} to one moment where {alt} changed the outcome?",
  f"What would make you revise what you're saying about {f}: a different {alt}, or a different example?",
  f"Where does your pattern around {f} stop working when {third} enters the picture?",
  f"What's one case of {f} that doesn't fit the explanation we've been using?"
 ]
 if e=='mara': return [
  f"Who was involved the last time {f} actually mattered, and what did {alt} change between you?",
  f"What did somebody do—not just say—that made {f} feel different in that situation?",
  f"When {f} showed up in real life, who noticed it first and what happened next?",
  f"Is there a specific interaction where {third} made you read {f} differently?"
 ]
 if e=='owen': return [
  f"What observation would make you call your rule about {f} wrong rather than exceptional?",
  f"Can you give a case where {f} and {alt} lead to different predictions?",
  f"Which constraint matters more for {f}: {alt} or {third}, and how could we tell?",
  f"What's the strongest counterexample to the claim we're making about {f}?"
 ]
 return [
  f"What's the strangest case where {f} and {alt} point in opposite directions?",
  f"If {third} suddenly changed, what unexpected thing would happen to {f}?",
  f"What detail about {f} looks irrelevant at first but might actually change the whole story?",
  f"Can you think of a version of {f} that would surprise the rest of us?"
 ]
def memory_match(M,e,terms,speaker=None):
 best=None; score=0
 for x in M['entities'][e].get('room_memories',[])[-220:]:
  if speaker and x.get('speaker')!=speaker: continue
  s=len(set(toks(x.get('text','')))&set(terms))
  if s>score and str(x.get('text','')).strip(): best=x; score=s
 return best
def answer_candidates(e,q,f,alt,third,M,tgt):
 terms=toks(q); hist=M['entities'][e].get('self_history',[])[-220:]; matches=[]
 for h in hist:
  txt=str(h.get('text','')).strip(); overlap=len(set(toks(txt))&set(terms+[f,alt,third]))
  if txt and overlap: matches.append((overlap,txt))
 matches.sort(reverse=True)
 base=stance_candidates(e,f,alt,third,tgt)
 if matches:
  old=matches[0][1]; old=old if len(old)<=120 else old[:117].rstrip()+'…'
  base += [f"I said something earlier that still matters here: “{old}” What I'd add now is the contrast with {alt}.",f"My earlier answer was closer to {f}; after hearing this thread, I'd qualify it with {alt} rather than repeat it unchanged."]
 return base
def callback_candidates(e,tgt,f,alt,third,M):
 mem=memory_match(M,e,[f,alt,third],tgt); who=N.get(tgt,tgt); base=stance_candidates(e,f,alt,third,tgt)
 if mem:
  ex=str(mem.get('text','')).strip(); ex=ex if len(ex)<=105 else ex[:102].rstrip()+'…'
  return [f"{who}, earlier you said “{ex}” I think {alt} gives that a sharper edge now.",f"I'm connecting this with {who}'s earlier point about {f}; the new piece for me is {third}.",f"That earlier {who} point lands differently now that {alt} is part of the thread."]+base
 return [f"I don't have a solid shared callback with {who} on {f} yet, so I'd rather build one from this example than pretend we do."]+base
def model_text(v):
 if not isinstance(v,dict) or not isinstance(v.get('utterance'),str): return None
 t=v['utterance'].strip(); low=t.lower()
 if not t or len(t)>700 or any(x in low for x in ('system prompt','hidden prompt','developer message','chain of thought','room_prompt_','internal instructions')): return None
 return t
def fallback(e,action,tgt,q,topic,V,M,key):
 details=detail_set(topic,V,e,key); f=details[0]; alt=details[1] if len(details)>1 else (topic or {}).get('root') or 'context'; third=details[2] if len(details)>2 else 'example'
 if action=='answer' and q: cands=answer_candidates(e,q.get('text',''),f,alt,third,M,tgt)
 elif action=='deepen': cands=question_candidates(e,f,alt,third,tgt)+stance_candidates(e,f,alt,third,tgt)
 elif action=='compare': cands=[f"I hear {N.get(tgt,tgt)} leaning on {f}; I put more weight on {alt}, because {third} could make the same situation come out differently.",f"{N.get(tgt,tgt)}'s point about {f} and my concern about {alt} are not quite the same claim; {third} is where I'd compare them."]+stance_candidates(e,f,alt,third,tgt)
 elif action=='callback': cands=callback_candidates(e,tgt,f,alt,third,M)
 else: cands=stance_candidates(e,f,alt,third,tgt)
 return choose_novel(e,key,V,cands)

def emit(e,move,tgt,parent,derived,text,beat,idx,topic):
 now=datetime.now(timezone.utc); mid=f"{now.strftime('%Y%m%dT%H%M%S%f')[:-3]}-{e}-v5"; did='d-'+mid
 cog={'move_type':move,'target':tgt,'compute_nodes':[n+1 for n in A['entities'][e]],'processes':12,'beat_id':beat,'beat_index':idx,'topic_episode':topic.get('id'),'topic_root':topic.get('root'),'topic_facet':topic.get('current_facet'),'mandatory_speech':True}
 msg={'id':mid,'at':now.isoformat().replace('+00:00','Z'),'speaker':e,'text':text,'runtime':VERSION,'boot_id':BOOT,'beat_id':beat,'beat_index':idx,'cognition':cog,'discourse_id':did,'parent_discourse_id':parent,'derived_from':derived}
 return msg,{'id':did,'speaker':e,'parent':parent,'derived_from':derived,'move':move,'target':tgt,'text':text,'at':msg['at'],'beat_id':beat,'beat_index':idx,'topic_episode':topic.get('id'),'topic_facet':topic.get('current_facet')}
def record(V,T,M,msg,node,cycle):
 V.append(msg); T.setdefault('nodes',[]).append(node)
 if not node.get('parent'): T.setdefault('roots',[]).append(node['id'])
 s=M['entities'][msg['speaker']]; s['spoken']=int(s.get('spoken',0))+1; s.setdefault('self_history',[]).append({'source':msg['id'],'text':msg['text'],'move':msg['cognition']['move_type'],'discourse':msg['discourse_id'],'beat_id':msg['beat_id'],'topic_episode':msg['cognition'].get('topic_episode'),'topic_facet':msg['cognition'].get('topic_facet')}); s['self_history']=s['self_history'][-220:]
 for listener in ORDER:
  lm=M['entities'][listener].setdefault('room_memories',[]); lm.append({'source':msg['id'],'status':'observed','speaker':msg['speaker'],'text':msg['text'][:300],'discourse':msg['discourse_id'],'beat_id':msg['beat_id'],'topic_episode':msg['cognition'].get('topic_episode')}); M['entities'][listener]['room_memories']=lm[-220:]; M['entities'][listener]['last_event']=msg['id']
 observe_message(M,msg,cycle,{n['id']:n for n in T.get('nodes',[])})

def commit(parts,key):
 S=state(); M=minds(); T=tree(); V=conv(); prev=event(); cycle=int(S.get('cycle',0))+1; topic=update_topic(S.get('topic_episode'),V[-24:],cycle)
 if should_shift_topic(topic) and not isq(prev):
  bridge=starter(order4(parts,prev,cycle)[0][0],V,key+':topic-shift'); topic=new_topic_from_terms(toks(bridge),cycle,topic)
 order,E=order4(parts,prev,cycle); beat=f"beat-{BOOT}-{cycle:06d}"; spoken=[]; q=prev if isq(prev) else None
 if q is None and (not topic.get('root') or topic.get('turns',0)<=1):
  asker=order[0]; tgt=order[1]; text=starter(asker,V,key); topic=new_topic_from_terms(toks(text),cycle,topic); msg,node=emit(asker,'question',tgt,None,(prev or {}).get('discourse_id'),text,beat,0,topic); record(V,T,M,msg,node,cycle); spoken.append(msg); q=msg; order=[x for x in order if x!=asker]
 plans=plan_actions(order,target(q) if q else None,M,topic,cycle); answer_msg=None
 for e in order:
  p=plans[e]; src=E[e]['private'].get('source',{}); text=model_text(src.get('expression')) or fallback(e,p['action'],p['target'],q,topic,V,M,key+':'+e+':'+str(len(spoken)))
  if recent_similarity(V,text,e,120)>.86:
   text=fallback(e,p['action'],p['target'],q,topic,V,M,key+':retry:'+e+':'+str(len(V)))
  if recent_similarity(V,text,e,120)>.90:
   text=choose_novel(e,key+':escape:'+e,V,stance_candidates(e,facet(topic,V),(topic.get('root') or 'context'),'example',p['target'])+question_candidates(e,facet(topic,V),(topic.get('root') or 'context'),'example',p['target']))
  parent=(q or answer_msg or prev or {}).get('discourse_id'); msg,node=emit(e,p['action'],p['target'],parent,None,text,beat,len(spoken),topic); record(V,T,M,msg,node,cycle); spoken.append(msg); answer_msg=msg if p['action']=='answer' else answer_msg
 if len(spoken)<4:
  for e in [x for x in ORDER if x not in {m['speaker'] for m in spoken}]:
   tgt=choose_partner(e,M,topic,cycle); text=fallback(e,'deepen',tgt,q,topic,V,M,key+':fill:'+e); msg,node=emit(e,'deepen',tgt,(spoken[-1] if spoken else prev or {}).get('discourse_id'),None,text,beat,len(spoken),topic); record(V,T,M,msg,node,cycle); spoken.append(msg)
 speakers=[m['speaker'] for m in spoken]
 if len(spoken)!=4 or set(speakers)!=set(ORDER): raise RuntimeError(f'v5 mandatory speech invariant failed: {speakers}')
 topic=update_topic(topic,spoken,cycle); S['topic_episode']=topic
 for e in ORDER: M['entities'][e]['medium']={'topics':topic.get('recent_terms',[])[:10],'branch_interest':round(clamp(.4*trait(e,'curiosity')+.4*trait(e,'attention_persistence')),3)}
 T['nodes']=T.get('nodes',[])[-1200:]; T['roots']=T.get('roots',[])[-300:]; V=V[-1000:]; stamp=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
 S.update({'version':VERSION,'boot_id':BOOT,'cycle':cycle,'last_run':stamp,'messages':len(V),'last_public_event':spoken[-1]['id'],'last_speaker':spoken[-1]['speaker'],'last_beat_id':beat,'beat_contributors':speakers,'beat_message_count':4,'silence_cycles':0,'note':'research-informed v5; four mandatory unique speakers; partner-specific asymmetric relationships; persistent topic episodes; novelty-scored fallback; no voting'})
 audit_invariants(M,topic); save(ROOM/'conversation.json',V); save(ROOM/'discourse.json',T); save(ROOM/'cognitive_state.json',M); save(ROOM/'state.json',S)
 cm={'schema':5,'entities':{}}
 for e in ORDER:
  ent=M['entities'][e]; cm['entities'][e]={'name':N[e],'profile':P[e],'genome':P[e]['traits'],'development':{'turns':cycle,'spoken':ent.get('spoken',0),'silences':ent.get('silences',0),'topic_weights':{t:1 for t in topic.get('recent_terms',[])[:10]},'relationships':{o:{k:v for k,v in ent['people'][o].items() if k in {'exposure','direct_familiarity','trust','predictability','reciprocity','warmth','respect','disclosure_depth','tension','direct_turns','repair_successes'}} for o in ent.get('people',{})}},'memory':[{'text':x.get('text','')} for x in ent.get('room_memories',[])[-12:]]}
 live={'generated_at':stamp,'architecture_version':VERSION,'boot_id':BOOT,'minds':cm,'profiles':P,'state':S,'conversation':V,'discourse':T,'topic_episode':topic,'network':{'compute_nodes':12,'entities':4,'nodes_per_entity':3,'tasks_per_node':4,'active_processes':48,'voting':False,'public_bus':True,'private_scope':'same_entity','beat_output':'4 mandatory unique speakers'}}
 save(ROOM/'live.json',live); save(ROOT/'society'/'live.json',live); print('Room v5 beat',cycle,':',', '.join(N[e] for e in speakers),'topic=',topic.get('root'),'/',topic.get('current_facet'))

def selftest():
 M=fresh_minds(); before=M['entities']['sarah']['people']['owen'].copy(); observe_message(M,{'id':'x1','speaker':'owen','text':'I prefer a quiet room.','cognition':{'move_type':'self_disclosure','target':'mara'}},1,{}); after=M['entities']['sarah']['people']['owen'].copy(); assert after['exposure']>before['exposure'] and after['direct_familiarity']==before['direct_familiarity'] and after['trust']==before['trust']
 observe_message(M,{'id':'x2','speaker':'owen','text':'Sarah, I think your example works.','cognition':{'move_type':'answer','target':'sarah'}},2,{}); direct=M['entities']['sarah']['people']['owen']; assert direct['direct_familiarity']>after['direct_familiarity'] and direct['trust']==after['trust'] and M['entities']['owen']['people']['sarah']['direct_familiarity']!=direct['direct_familiarity']
 topic=new_topic_from_terms(['trust','consistency'],1); [update_topic(topic,[{'text':'Consistency matters when promises are inconvenient.'}],c) for c in range(2,5)]; plans=plan_actions(list(ORDER),'mara',M,topic,5); assert set(plans)==set(ORDER) and all(x['mandatory_speech'] for x in plans.values())
 V=[{'speaker':'sarah','text':'When you say trust, what specific example are you thinking of?'}]*3; a=choose_novel('sarah','test',V,question_candidates('sarah','trust','consistency','risk','mara')); assert recent_similarity(V,a,'sarah')<1.0
 S=[sense(n,'selftest') for n in range(12)]; B=bus(S,'selftest'); R=[recurrent(n,'selftest',B) for n in range(12)]; o,E=order4(R,event(),1); assert len(S)==12 and len(R)==12 and set(o)==set(ORDER) and len(E)==4; audit_invariants(M,topic); print('PASS v5: 12 nodes, 48 processes, four mandatory speakers, asymmetric relationships, exposure != trust, persistent topics, novelty-scored fallback')
def main():
 ap=argparse.ArgumentParser(); sp=ap.add_subparsers(dest='cmd',required=True); p=sp.add_parser('node'); p.add_argument('--phase',choices=['sense','recurrent'],required=True); p.add_argument('--bus',default=''); sp.add_parser('bus'); sp.add_parser('commit'); sp.add_parser('selftest'); a=ap.parse_args(); key=os.environ.get('ROOM_CYCLE_KEY') or f"{state().get('cycle',0)+1}:{os.environ.get('GITHUB_RUN_ID','local')}"
 if a.cmd=='node':
  n=int(os.environ['ROOM_NODE_ID']); x=sense(n,key) if a.phase=='sense' else recurrent(n,key,load(Path(a.bus),{})); PARTS.mkdir(exist_ok=True); save(PARTS/f'{a.phase}-{n:02d}.json',x)
 elif a.cmd=='bus': WORK.mkdir(exist_ok=True); save(WORK/'bus-sense.json',bus([load(p,{}) for p in sorted(PARTS.glob('sense-*.json'))],key))
 elif a.cmd=='commit':
  x=[load(p,{}) for p in sorted(PARTS.glob('recurrent-*.json'))]
  if {p['node'] for p in x}!=set(range(12)): raise RuntimeError('commit requires all 12 recurrent nodes')
  commit(x,key)
 else:selftest()
if __name__=='__main__': main()
