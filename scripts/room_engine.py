#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json, os, random, re
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; ROOM=ROOT/'room'; PARTS=ROOT/'room_parts'; WORK=ROOT/'room_work'
CFG=json.loads((ROOM/'config.json').read_text()); A=CFG['a']; P=CFG['p']; ORDER=('sarah','mara','owen','jules'); N={e:P[e]['name'] for e in ORDER}
MEM={e:[{'id':r[0],'types':r[1],'age':r[2],'text':r[3],'tags':r[4],'sal':r[5],'emo':r[6],'conf':r[7]} for r in CFG['m'][e]] for e in ORDER}
STOP=set('the and but for not was are you your our out too did can got one once that this with from have has had just what when where there they them then than about would could should into only really some more very like because been being does doing done will well yeah okay also still maybe kind sort thing things something anything someone everyone say saying think thinking thought know knowing mean means seem seems want wants wanted make making made start starting started try trying tried good great nice sure right actually probably pretty little much many few around again already even ever never always often sometimes today tonight tomorrow yesterday different together interesting going everything current'.split())

def load(p,d): return json.loads(p.read_text()) if p.exists() else d
def save(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def seed(*x): return int(hashlib.sha256(':'.join(map(str,x)).encode()).hexdigest()[:16],16)&0x7fffffff
def rng(*x): return random.Random(seed(*x))
def clamp(x,a=0,b=1): return max(a,min(b,float(x)))
def toks(s):
    out=[]; names={v.lower() for v in N.values()}
    for w in re.findall(r"[a-z][a-z'-]{2,}",str(s or '').lower()):
        w=w.strip("'-")
        if w and w not in STOP and w not in names and w not in out: out.append(w)
    return out

def init():
    ROOM.mkdir(exist_ok=True)
    if not (ROOM/'conversation.json').exists(): save(ROOM/'conversation.json',[])
    if not (ROOM/'discourse.json').exists(): save(ROOM/'discourse.json',{'nodes':[],'roots':[]})
    if not (ROOM/'state.json').exists(): save(ROOM/'state.json',{'version':'room-cognition-v3','cycle':0,'silence_cycles':0,'last_speaker':None})
    if not (ROOM/'cognitive_state.json').exists():
        E={}
        for e in ORDER:
            E[e]={'fast':{'activation':.2,'attention':[]},'medium':{'topics':[],'branch_interest':0},'slow':{'social_energy':.55},'noise':{'activation':0,'association':0,'inhibition':0,'social':0},'room_memories':[],'self_history':[],'last_event':None,'spoken':0,'silences':0,'people':{o:{'familiarity':.02,'reports':[]} for o in ORDER if o!=e}}
        save(ROOM/'cognitive_state.json',{'entities':E})
init()

def conv(): return load(ROOM/'conversation.json',[])
def msgs(): return [m for m in conv() if str(m.get('runtime','')).startswith('room-cognition-v')]
def event():
    m=msgs(); return m[-1] if m else None
def state(): return load(ROOM/'state.json',{})
def minds(): return load(ROOM/'cognitive_state.json',{'entities':{}})
def tree(): return load(ROOM/'discourse.json',{'nodes':[],'roots':[]})
def trait(e,k,d=.5): return float(P[e]['traits'].get(k,d))
def node_info(n):
    e=ORDER[n//3]; local=n%3; role,tasks=A['roles'][str(local)]; return e,local,role,tasks

def target(m):
    if not m:return None
    t=(m.get('cognition') or {}).get('target')
    if t:return t
    low=m.get('text','').lower()
    for e,name in N.items():
        if e!=m.get('speaker') and re.search(rf'\b{re.escape(name.lower())}\b',low): return e
    return None

def asked(e,m): return bool(m and m.get('speaker')!=e and m.get('text','').rstrip().endswith('?') and target(m) in (None,e))
def mem_by_id(e,i): return next((m for m in MEM[e] if m['id']==i),None)
def recall(e,cues,key):
    q=set(cues); ranked=sorted(MEM[e],key=lambda m:2*len(q&set(m['tags']))+.5*m['sal']+.25*m['emo'],reverse=True)
    if q and ranked and q&set(ranked[0]['tags']): return ranked[0]
    return rng('recall',e,key).choice(sorted(MEM[e],key=lambda m:m['sal'],reverse=True)[:6])

def noise(e,s,key):
    old=s.get('noise',{}); r=rng('noise',e,key); scales={'activation':.08,'association':.09,'inhibition':.07,'social':.08}; aliases={'activation':'a','association':'x','inhibition':'i','social':'s'}
    return {k:round(clamp(.82*float(old.get(k,old.get(aliases[k],0)))+r.gauss(0,v),-.25,.25),4) for k,v in scales.items()}

def discourse_depth(i,T=None):
    T=T or tree(); mp={n['id']:n for n in T['nodes']}; seen=set(); d=0
    while i and i in mp and i not in seen and d<20: seen.add(i); d+=1; i=mp[i].get('parent')
    return d

def resolve_anchor(m,T=None,M=None):
    '''Find the autobiographical/factual memory anchoring a discourse branch.
    Reaction/question memory samples are never treated as public branch content.'''
    if not m:return (None,None)
    c=m.get('cognition') or {}
    if c.get('branch_memory'): return c.get('branch_owner'),c.get('branch_memory')
    if c.get('move_type') in {'self_disclosure','new_root'} and c.get('memory_provenance'): return m.get('speaker'),c.get('memory_provenance')
    T=T or tree(); M=M or msgs(); mp={n['id']:n for n in T['nodes']}; by_d={x.get('discourse_id'):x for x in M if x.get('discourse_id')}; i=m.get('discourse_id'); seen=set()
    while i and i in mp and i not in seen:
        seen.add(i); n=mp[i]
        if n.get('branch_memory'): return n.get('branch_owner'),n.get('branch_memory')
        h=by_d.get(i,{ }); hc=h.get('cognition') or {}
        if hc.get('branch_memory'): return hc.get('branch_owner'),hc.get('branch_memory')
        if hc.get('move_type') in {'self_disclosure','new_root'} and hc.get('memory_provenance'): return h.get('speaker'),hc.get('memory_provenance')
        i=n.get('parent') or n.get('derived_from')
    return None,None

def sense(n,key):
    e,local,role,tasks=node_info(n); m=event(); S=minds()['entities'][e]; kw=toks((m or {}).get('text',''))[:8]; rec=recall(e,kw,key); z=noise(e,S,key); r=rng('sense',key,n); bo,bm=resolve_anchor(m)
    if role=='comprehension':
        head=(re.findall(r"[a-z']+",(m or {}).get('text','').lower()) or [''])[0]; pred={'why':'cause','how':'process','where':'place','when':'time','who':'person','what':'explanation'}.get(head)
        work={tasks[0]:[{'concept':w,'activation':round(.7+.2*trait(e,'curiosity'),3)} for w in kw],tasks[1]:{'kind':'hierarchical_utterance','clauses':[{'tokens':toks(x)} for x in re.split(r'[,;!?]|\s+(?:but|because|and)\s+',(m or {}).get('text','')) if x.strip()][:6]},tasks[2]:{'scope':'constituent','expected':pred},tasks[3]:{'speaker':(m or {}).get('speaker'),'target':target(m),'branch_owner':bo,'branch_memory':bm}}
        ready=.10; att=clamp(.4+.3*trait(e,'social_sensitivity')+(.15 if m else-.1)+r.gauss(0,.04)); pub=kw
    elif role=='thought':
        work={tasks[0]:{'concepts':kw+rec['tags'][:4],'breadth':round(clamp(trait(e,'openness')+z['association']),3)},tasks[1]:{'operation':'merge','left':kw,'right':rec['tags']},tasks[2]:rec,tasks[3]:{'arousal':round(clamp(.15+.4*trait(e,'emotional_reactivity')+.2*rec['emo']),3)}}
        ready=.2+.1*trait(e,'self_disclosure'); att=clamp(.32+.35*trait(e,'curiosity')+r.gauss(0,.05)); pub=[]
    else:
        q=asked(e,m); ready=clamp(.2+.26*trait(e,'extraversion')+.24*trait(e,'curiosity')+.18*trait(e,'self_disclosure')-.23*trait(e,'inhibition')+(.52 if q else 0)-(.3 if m and m.get('speaker')==e else 0)+z['social']-.45*z['inhibition']+r.gauss(0,.04)); att=clamp(.3+.25*trait(e,'social_sensitivity')+(.2 if q else 0)); work={tasks[0]:{'direct_question':q},tasks[1]:{'moves':['answer'] if q else ['follow_up','self_disclosure','reaction','new_root']},tasks[2]:{'readiness':ready},tasks[3]:{'silence_available':True}}; pub=[]
    return {'phase':'sense','node':n,'entity':e,'local':local,'role':role,'tasks':tasks,'private':{'event':m,'keywords':kw,'memory':rec,'noise':z,'work':work,'branch_owner':bo,'branch_memory':bm},'public':{'node':n,'entity':e,'role':role,'attention':round(att,3),'readiness':round(ready,3),'concepts':pub}}

def bus(parts,key):
    if {p['node'] for p in parts}!=set(range(12)): raise RuntimeError('all 12 cognitive nodes are required')
    public=[p['public'] for p in sorted(parts,key=lambda p:p['node'])]; expr=[x for x in public if x['role']=='expression']; concepts=[]
    for p in public:
        for w in p.get('concepts',[]):
            if w not in concepts: concepts.append(w)
    return {'key':key,'public':public,'private':{e:[p for p in parts if p['entity']==e] for e in ORDER},'network':{'mean_attention':round(sum(p.get('attention',0) for p in public)/12,4),'mean_expression':round(sum(p.get('readiness',0) for p in expr)/4,4),'expression':{p['entity']:p.get('readiness',0) for p in expr},'concepts':concepts[:12]}}
def rp(B,e,role): return next(p for p in B['private'][e] if p['role']==role)

def question(e,m,key):
    low=(m or {}).get('text','').lower()
    if any(w in low for w in ('mother','father','sister','brother','friend','cousin','coworker','partner')): choices=['Were you close?','What were they like?','How did you two know each other?']
    elif any(w in low for w in ('city','town','house','apartment','school','ocean','mountain','place')): choices=['What was that place like?','Do you miss anything about it?','What do you remember most about being there?']
    elif any(w in low for w in ('felt','afraid','angry','sad','happy','love','hated','miss')): choices=['How did that affect you?','Did that bother you at the time?','Do you still feel that way?']
    else: choices=['What happened after that?','How did that happen?','Has that changed much since then?']
    return rng('question',e,key,*toks(low)).choice(choices)

def move(e,m,key):
    if asked(e,m): return 'answer'
    if not m:return 'self_disclosure'
    r=rng('move',e,key); cur=(m.get('cognition') or {}).get('move_type'); depth=discourse_depth(m.get('discourse_id'))
    w={'follow_up':.52+.34*trait(e,'curiosity'),'self_disclosure':.22+.32*trait(e,'self_disclosure'),'reaction':.24+.22*trait(e,'agreeableness'),'new_root':.02+.10*trait(e,'novelty_seeking')}
    if cur in {'self_disclosure','answer'}: w['follow_up']+=.20
    elif cur=='reaction': w['follow_up']*=.25; w['self_disclosure']+=.22; w['new_root']+=.10
    if depth>=4: w['new_root']+=.38; w['follow_up']*=.78
    if m.get('speaker')==e: w['follow_up']*=.35; w['reaction']*=.55; w['new_root']+=.15
    x=r.random()*sum(w.values()); s=0
    for k,v in w.items():
        s+=v
        if x<=s:return k
    return 'reaction'

def recurrent(n,key,B):
    e,local,role,tasks=node_info(n); C=rp(B,e,'comprehension'); H=rp(B,e,'thought'); X=rp(B,e,'expression'); m=C['private']['event']; rec=H['private']['memory']; bo=C['private'].get('branch_owner'); bm=C['private'].get('branch_memory'); net=B['network']; r=rng('recur',key,n)
    if role=='comprehension':
        co=list(dict.fromkeys(C['private']['keywords']+net['concepts']+rec['tags']))[:12]; work={tasks[0]:{'coactive':co},tasks[1]:C['private']['work'][tasks[1]],tasks[2]:C['private']['work'][tasks[2]],tasks[3]:{'branch_owner':bo,'branch_memory':bm,'network_attention':net['mean_attention']}}; ready=0; intent=None
    elif role=='thought':
        work={tasks[0]:{'concepts':list(dict.fromkeys(C['private']['keywords']+net['concepts']+rec['tags']))[:12]},tasks[1]:H['private']['work'][tasks[1]],tasks[2]:rec,tasks[3]:H['private']['work'][tasks[3]]}; ready=.2; intent=None
    else:
        mv=move(e,m,key); ready=clamp(X['public']['readiness']+r.gauss(0,.025)); crowd=sum(v for peer,v in net['expression'].items() if peer!=e)/3
        use=mem_by_id(e,bm) if mv=='answer' and bo==e and bm else rec
        if not use: use=rec
        if mv in {'self_disclosure','new_root'}: out_bo,out_bm=e,use['id']
        else: out_bo,out_bm=bo,bm
        if mv=='answer': tgt=(m or {}).get('speaker')
        elif mv=='follow_up': tgt=bo if bo and bo!=e else (m or {}).get('speaker')
        elif mv=='reaction': tgt=(m or {}).get('speaker')
        else:tgt=None
        intent={'move':mv,'target':tgt,'memory':use['id'],'concepts':use['tags'][:6],'question':question(e,m,key) if mv=='follow_up' else None,'readiness':round(ready,3),'parent':(m or {}).get('discourse_id'),'branch_owner':out_bo,'branch_memory':out_bm,'latency':round(max(.05,1.55-1.15*ready+.35*trait(e,'inhibition')+.18*crowd+r.uniform(0,.22)+(.55 if m and m.get('speaker')==e else 0)),4)}
        work={tasks[0]:{'intent':mv},tasks[1]:intent,tasks[2]:{'readiness':ready,'latency':intent['latency']},tasks[3]:{'provenance':True,'silence_available':True,'network_crowding':round(crowd,3)}}
    return {'phase':'recurrent','node':n,'entity':e,'local':local,'role':role,'tasks':tasks,'private':{'work':work,'intent':intent},'public':{'node':n,'entity':e,'role':role,'readiness':round(ready,3)}}

def answer(e,I,m,key):
    mm=mem_by_id(e,I.get('branch_memory')) or mem_by_id(e,I.get('memory')); q=(m or {}).get('text','').lower(); r=rng('answer',e,key,q)
    if mm:
        t=mm['text'].rstrip('.'); low=t.lower()
        if 'were you close' in q and 'best friend' in low:return 'Yeah. We were best friends.','memory'
        if 'how did you two know' in q and 'best friend' in low:return "We were already best friends by then, but I don't really remember how we first met.",'memory'
        if 'what were they like' in q:return "I remember the relationship more clearly than their personality.",'memory'
        if 'do you miss' in q:return "I remember it clearly, but I don't think I ever decided whether I miss it.",'memory'
        return 'The part I remember is that I '+t+'.','memory'
    return r.choice(["I don't really remember that part.","I'm not sure about that detail."]),'grounded'

def externalize(e,I,m,key):
    r=rng('surface',e,key,I['move']); mm=mem_by_id(e,I.get('memory'))
    if I['move']=='follow_up':return I['question'],'structured'
    if I['move']=='answer':return answer(e,I,m,key)
    if I['move'] in {'self_disclosure','new_root'} and mm:return r.choice(['I ','That reminds me that I ','Randomly, I '])+mm['text'].rstrip('.')+'.','memory'
    return r.choice(['That part caught my attention.','I can see why that would stick with you.',"I hadn't thought about it that way."]),'structured'

def eligible(parts,m):
    E=[p for p in parts if p['role']=='expression' and p['private'].get('intent')]; t=target(m) if m and m.get('text','').rstrip().endswith('?') else None
    if t:
        z=[p for p in E if p['entity']==t]
        if z:return [p for p in z if p['private']['intent']['readiness']>=.34]
    return [p for p in E if p['private']['intent']['readiness']>=.48]

def commit(parts,key):
    S=state(); Minds=minds(); T=tree(); V=conv(); m=event()
    for e in ORDER:
        es=Minds['entities'][e]; ep=[p for p in parts if p['entity']==e]; es['noise']=noise(e,es,key); c=next(p for p in ep if p['role']=='comprehension'); co=c['private']['work'][c['tasks'][0]]['coactive']; es.setdefault('fast',{})['activation']=round(sum(p['public']['readiness'] for p in ep)/3,3); es['fast']['attention']=co[:8]; es.setdefault('medium',{})['topics']=co[:8]; es['medium']['branch_interest']=round(clamp(.4*trait(e,'curiosity')+.4*trait(e,'attention_persistence')),3)
        if m and es.get('last_event')!=m['id']:
            bo,bm=resolve_anchor(m); obs={'source':m['id'],'status':'observed','speaker':m['speaker'],'text':m['text'][:300],'discourse':m.get('discourse_id'),'branch_owner':bo,'branch_memory':bm}; es.setdefault('room_memories',[]).append(obs); es['room_memories']=es['room_memories'][-120:]
            if m['speaker']!=e:
                pm=es.setdefault('people',{}).setdefault(m['speaker'],{'familiarity':.02,'reports':[]}); pm['familiarity']=round(clamp(pm.get('familiarity',.02)+.018),3); pm.setdefault('reports',[]).append({'source':m['id'],'status':'reported','text':m['text'][:300],'branch_owner':bo,'branch_memory':bm}); pm['reports']=pm['reports'][-60:]
            es['last_event']=m['id']
    q=sorted([(p['private']['intent']['latency'],ORDER.index(p['entity']),p) for p in eligible(parts,m)],key=lambda x:(x[0],x[1])); spoken=None; now=datetime.now(timezone.utc); stamp=now.isoformat().replace('+00:00','Z')
    if q:
        p=q[0][2]; e=p['entity']; I=p['private']['intent']; text,mode=externalize(e,I,m,key); mid=f"{now.strftime('%Y%m%dT%H%M%S')}-{e}-v3"; parent=I.get('parent'); derived=None
        if I['move']=='new_root' or (parent and discourse_depth(parent,T)>=A['discourse']['max_depth']): derived=parent; parent=None
        did='d-'+mid; cog={'move_type':I['move'],'target':I.get('target'),'memory_provenance':I.get('memory'),'branch_owner':I.get('branch_owner'),'branch_memory':I.get('branch_memory'),'externalization':mode,'compute_nodes':[n+1 for n in A['entities'][e]],'processes':12}
        spoken={'id':mid,'at':stamp,'speaker':e,'text':text,'runtime':'room-cognition-v3','cognition':cog,'discourse_id':did,'parent_discourse_id':parent,'derived_from':derived}; V.append(spoken); T['nodes'].append({'id':did,'speaker':e,'parent':parent,'derived_from':derived,'move':I['move'],'target':I.get('target'),'branch_owner':I.get('branch_owner'),'branch_memory':I.get('branch_memory'),'text':text,'at':stamp}); T['nodes']=T['nodes'][-600:]
        if not parent:T.setdefault('roots',[]).append(did); T['roots']=T['roots'][-160:]
        es=Minds['entities'][e]; es['spoken']=es.get('spoken',0)+1; es.setdefault('self_history',[]).append({'source':mid,'text':text,'move':I['move'],'memory':I.get('memory'),'branch_memory':I.get('branch_memory'),'discourse':did}); es['self_history']=es['self_history'][-120:]; S['last_speaker']=e; S['silence_cycles']=0
    else:
        S['silence_cycles']=S.get('silence_cycles',0)+1
        for e in ORDER:Minds['entities'][e]['silences']=Minds['entities'][e].get('silences',0)+1
    S.update({'version':'room-cognition-v3','cycle':S.get('cycle',0)+1,'last_run':stamp,'messages':len(V),'last_public_event':spoken['id'] if spoken else (m or {}).get('id'),'note':'4 separate entities; 12 nodes x 4 tasks = 48 processes; public bus; private entity state; no voting'}); V=V[-520:]
    save(ROOM/'conversation.json',V); save(ROOM/'discourse.json',T); save(ROOM/'cognitive_state.json',Minds); save(ROOM/'state.json',S)
    cm={'schema':3,'entities':{e:{'name':N[e],'profile':P[e],'genome':P[e]['traits'],'development':{'turns':S['cycle'],'spoken':Minds['entities'][e].get('spoken',0),'silences':Minds['entities'][e].get('silences',0),'response_length_ema':0,'topic_weights':{t:1 for t in Minds['entities'][e].get('medium',{}).get('topics',[])},'relationships':{o:v.get('familiarity',0) for o,v in Minds['entities'][e].get('people',{}).items()},'lifetime_memory_count':len(MEM[e])},'memory':[{'text':x['text']} for x in Minds['entities'][e].get('room_memories',[])[-8:]]} for e in ORDER}}
    live={'generated_at':stamp,'architecture_version':'room-cognition-v3','minds':cm,'profiles':P,'state':S,'conversation':V,'discourse':T,'network':{'compute_nodes':12,'entities':4,'nodes_per_entity':3,'tasks_per_node':4,'active_processes':48,'voting':False,'public_bus':True,'private_scope':'same_entity'}}; save(ROOM/'live.json',live); save(ROOT/'society'/'live.json',live); print(f"{N[spoken['speaker']]}: {spoken['cognition']['move_type']}" if spoken else 'Room silent; all 12 nodes processed')

def selftest():
    sensed=[sense(n,'test') for n in range(12)]; B=bus(sensed,'test'); rec=[recurrent(n,'test',B) for n in range(12)]; assert len(rec)==12 and len(B['public'])==12 and all(len(B['private'][e])==3 for e in ORDER) and A['network']['voting'] is False and set(B['network']['expression'])==set(ORDER)
    disclosure={'speaker':'mara','runtime':'room-cognition-v2','discourse_id':'d1','cognition':{'move_type':'self_disclosure','memory_provenance':'mara-004'}}; reaction={'speaker':'jules','runtime':'room-cognition-v2','discourse_id':'d2','cognition':{'move_type':'reaction','memory_provenance':'jules-004'}}; T={'nodes':[{'id':'d1','parent':None},{'id':'d2','parent':'d1'}],'roots':['d1']}; assert resolve_anchor(reaction,T,[disclosure,reaction])==('mara','mara-004'); assert all(len({k for m in MEM[e] for k in m['types']})>=10 for e in ORDER); print('PASS 4 entities x 3 nodes x 4 tasks; 12-node public bus; private entity scope; reaction-safe provenance; bounded discourse; no voting')

def main():
    ap=argparse.ArgumentParser(); sp=ap.add_subparsers(dest='cmd',required=True); p=sp.add_parser('node'); p.add_argument('--phase',choices=['sense','recurrent'],required=True); p.add_argument('--bus',default=''); sp.add_parser('bus'); sp.add_parser('commit'); sp.add_parser('selftest'); a=ap.parse_args(); key=os.environ.get('ROOM_CYCLE_KEY') or f"{state().get('cycle',0)+1}:{os.environ.get('GITHUB_RUN_ID','local')}"
    if a.cmd=='node':
        n=int(os.environ['ROOM_NODE_ID']); x=sense(n,key) if a.phase=='sense' else recurrent(n,key,load(Path(a.bus),{})); PARTS.mkdir(exist_ok=True); save(PARTS/f'{a.phase}-{n:02d}.json',x)
    elif a.cmd=='bus': WORK.mkdir(exist_ok=True); save(WORK/'bus-sense.json',bus([load(p,{}) for p in sorted(PARTS.glob('sense-*.json'))],key))
    elif a.cmd=='commit':
        x=[load(p,{}) for p in sorted(PARTS.glob('recurrent-*.json'))]
        if {p['node'] for p in x}!=set(range(12)):raise RuntimeError('commit requires all 12 recurrent nodes')
        commit(x,key)
    else:selftest()
if __name__=='__main__':main()
