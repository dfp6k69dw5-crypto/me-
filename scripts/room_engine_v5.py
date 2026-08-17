#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,os,random,re
from datetime import datetime,timezone
from pathlib import Path
from room_private_model import run as model_run
from room_social_v5 import ORDER,audit_invariants,choose_partner,migrate_minds,migrate_state,new_topic_from_terms,observe_message,plan_actions,should_shift_topic,topic_terms_from_messages,update_topic

ROOT=Path(__file__).resolve().parents[1]; ROOM=ROOT/'room'; PARTS=ROOT/'room_parts'; WORK=ROOT/'room_work'
CFG=json.loads((ROOM/'config.json').read_text()); A=CFG['a']; P=CFG['p']; BOOT=CFG.get('boot_id','room-default'); VERSION='room-cognition-v5'; N={e:P[e]['name'] for e in ORDER}
STOP=set('the and but for not was are you your our out too did can got one once that this with from have has had just what when where there they them then than about would could should into only really some more very like because been being does doing done will well yeah okay also still maybe kind sort thing things something anything someone everyone say saying think thinking thought know knowing mean means seem seems want wants wanted make making made start starting started try trying tried good great nice sure right actually probably pretty little much many few around again already even ever never always often sometimes today tonight tomorrow yesterday different together interesting going everything current'.split())

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

STARTERS=["What's a specific example of something you've changed your mind about?","What's a place you remember mainly because of one small detail?","What's a skill you respect more after trying it yourself?","What's something people often call simple that doesn't feel simple to you?","What's a routine you keep because it actually works for you?","What's a disagreement that taught you something useful?"]
def same(V,text):
 n=re.sub(r'\W+',' ',text.lower()).strip(); return any(re.sub(r'\W+',' ',str(m.get('text','')).lower()).strip()==n for m in V[-120:])
def starter(e,V,key): return rr('starter-v5',e,key).choice([x for x in STARTERS if not same(V,x)] or STARTERS)
def facet(topic,V): return (topic or {}).get('current_facet') or (topic_terms_from_messages(V[-12:]) or ['that'])[0]
def stance(e,f): return {'sarah':f"What catches me about {f} is the pattern underneath it",'mara':f"With {f}, I keep noticing what it does between people",'owen':f"For {f}, I want to separate the rule from the exception",'jules':f"The interesting part of {f} to me is the weird edge case"}[e]
def question(e,f,terms):
 alt=next((x for x in terms if x!=f),None)
 if e=='sarah': return f"When you say {f}, what specific example are you thinking of?"
 if e=='mara': return f"What actually happened the last time {f} mattered between you and somebody else?"
 if e=='owen': return f"What would count as a clear exception to what you're saying about {f}?"
 return f"How do {f} and {alt} pull in different directions for you?" if alt else f"What unexpected detail would change how you see {f}?"
def memory_match(M,e,terms,speaker=None):
 best=None; score=0
 for x in M['entities'][e].get('room_memories',[])[-160:]:
  if speaker and x.get('speaker')!=speaker: continue
  s=len(set(toks(x.get('text','')))&set(terms))
  if s>score: best=x; score=s
 return best
def answer(e,q,f,M):
 terms=toks(q); hist=M['entities'][e].get('self_history',[])[-180:]; matches=sorted(((len(set(toks(h.get('text','')))&set(terms+[f])),h.get('text','')) for h in hist),reverse=True)
 if matches and matches[0][0]>0: return matches[0][1]
 return stance(e,f)+". I don't have a clean example yet, but I'd rather stay with that detail than jump to another broad subject."
def model_text(v):
 if not isinstance(v,dict) or not isinstance(v.get('utterance'),str): return None
 t=v['utterance'].strip(); low=t.lower()
 if not t or len(t)>700 or any(x in low for x in ('system prompt','hidden prompt','developer message','chain of thought','room_prompt_','internal instructions')): return None
 return t
def fallback(e,action,tgt,q,topic,V,M):
 f=facet(topic,V); terms=topic.get('recent_terms',[]) if topic else []
 if action=='answer' and q: return answer(e,q.get('text',''),f,M)
 if action=='deepen': return question(e,f,terms)
 if action=='compare': return f"I hear {N.get(tgt,tgt)} emphasizing {f}. {stance(e,f)}; I'd want to test whether it still holds in one concrete example."
 if action=='callback':
  mem=memory_match(M,e,[f]+list(terms),tgt)
  if mem:
   ex=str(mem.get('text','')).strip(); ex=ex if len(ex)<=110 else ex[:107].rstrip()+'…'
   return f"This connects for me to something {N.get(tgt,tgt)} said earlier: “{ex}” The part I want to carry forward is {f}."
  return stance(e,f)+". I want to keep that thread alive rather than reset the conversation."
 return stance(e,f)+'.'

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
 if should_shift_topic(topic): topic=new_topic_from_terms([x for x in topic_terms_from_messages(V[-12:]) if x!=topic.get('current_facet')],cycle,topic)
 order,E=order4(parts,prev,cycle); beat=f"beat-{BOOT}-{cycle:06d}"; spoken=[]; q=prev if isq(prev) else None
 if q is None and not topic.get('root'):
  asker=order[0]; tgt=order[1]; text=starter(asker,V,key); topic=new_topic_from_terms(toks(text),cycle,topic); msg,node=emit(asker,'question',tgt,None,(prev or {}).get('discourse_id'),text,beat,0,topic); record(V,T,M,msg,node,cycle); spoken.append(msg); q=msg; order=[x for x in order if x!=asker]
 plans=plan_actions(order,target(q) if q else None,M,topic,cycle); answer_msg=None
 for e in order:
  p=plans[e]; src=E[e]['private'].get('source',{}); text=model_text(src.get('expression')) or fallback(e,p['action'],p['target'],q,topic,V,M)
  if same(V,text): text=question(e,facet(topic,V),topic.get('recent_terms',[])) if p['action']!='answer' else answer(e,(q or {}).get('text',''),facet(topic,V),M)
  parent=(q or answer_msg or prev or {}).get('discourse_id'); msg,node=emit(e,p['action'],p['target'],parent,None,text,beat,len(spoken),topic); record(V,T,M,msg,node,cycle); spoken.append(msg); answer_msg=msg if p['action']=='answer' else answer_msg
 if len(spoken)<4:
  for e in [x for x in ORDER if x not in {m['speaker'] for m in spoken}]:
   tgt=choose_partner(e,M,topic,cycle); text=question(e,facet(topic,V),topic.get('recent_terms',[])); msg,node=emit(e,'deepen',tgt,(spoken[-1] if spoken else prev or {}).get('discourse_id'),None,text,beat,len(spoken),topic); record(V,T,M,msg,node,cycle); spoken.append(msg)
 speakers=[m['speaker'] for m in spoken]
 if len(spoken)!=4 or set(speakers)!=set(ORDER): raise RuntimeError(f'v5 mandatory speech invariant failed: {speakers}')
 topic=update_topic(topic,spoken,cycle); S['topic_episode']=topic
 for e in ORDER: M['entities'][e]['medium']={'topics':topic.get('recent_terms',[])[:10],'branch_interest':round(clamp(.4*trait(e,'curiosity')+.4*trait(e,'attention_persistence')),3)}
 T['nodes']=T.get('nodes',[])[-1200:]; T['roots']=T.get('roots',[])[-300:]; V=V[-1000:]; stamp=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
 S.update({'version':VERSION,'boot_id':BOOT,'cycle':cycle,'last_run':stamp,'messages':len(V),'last_public_event':spoken[-1]['id'],'last_speaker':spoken[-1]['speaker'],'last_beat_id':beat,'beat_contributors':speakers,'beat_message_count':4,'silence_cycles':0,'note':'research-informed v5; four mandatory unique speakers; partner-specific asymmetric relationships; persistent topic episodes; no voting'})
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
 S=[sense(n,'selftest') for n in range(12)]; B=bus(S,'selftest'); R=[recurrent(n,'selftest',B) for n in range(12)]; o,E=order4(R,event(),1); assert len(S)==12 and len(R)==12 and set(o)==set(ORDER) and len(E)==4; audit_invariants(M,topic); print('PASS v5: 12 nodes, 48 processes, four mandatory speakers, asymmetric relationships, exposure != trust, persistent topic episodes')
def main():
 ap=argparse.ArgumentParser(); sp=ap.add_subparsers(dest='cmd',required=True); p=sp.add_parser('node'); p.add_argument('--phase',choices=['sense','recurrent'],required=True); p.add_argument('--bus',default=''); sp.add_parser('bus'); sp.add_parser('commit'); sp.add_parser('selftest'); a=ap.parse_args(); key=os.environ.get('ROOM_CYCLE_KEY') or f"{state().get('cycle',0)+1}:{os.environ.get('GITHUB_RUN_ID','local')}"
 if a.cmd=='node':
  n=int(os.environ['ROOM_NODE_ID']); x=sense(n,key) if a.phase=='sense' else recurrent(n,key,load(Path(a.bus),{})); PARTS.mkdir(exist_ok=True); save(PARTS/f'{a.phase}-{n:02d}.json',x)
 elif a.cmd=='bus': WORK.mkdir(exist_ok=True); save(WORK/'bus-sense.json',bus([load(p,{}) for p in sorted(PARTS.glob('sense-*.json'))],key))
 elif a.cmd=='commit':
  x=[load(p,{}) for p in sorted(PARTS.glob('recurrent-*.json'))]
  if {p['node'] for p in x}!=set(range(12)): raise RuntimeError('commit requires all 12 recurrent nodes')
  commit(x,key)
 else: selftest()
if __name__=='__main__': main()
