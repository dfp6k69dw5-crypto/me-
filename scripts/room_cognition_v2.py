#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,os,random,re,subprocess
from datetime import datetime,timezone
from pathlib import Path
R=Path(__file__).resolve().parents[1];D=R/"room";P=R/"room_parts";W=R/"room_work"
C=json.loads((D/"config.json").read_text());A=C["a"];Q=C["p"];O=("sarah","mara","owen","jules");N={e:Q[e]["name"] for e in O}
M={e:[{"id":x[0],"types":x[1],"age":x[2],"first":x[3],"tags":x[4],"sal":x[5],"emo":x[6],"conf":x[7]} for x in C["m"][e]] for e in O}
STOP=set("the and but for not was are you your our out too did can got one once that this with from have has had just what when where there they them then than about would could should into only really some more very like because been being does doing done will well yeah okay also still maybe kind sort thing things something anything someone everyone say saying think thinking thought know knowing mean means seem seems want wants wanted make making made start starting started try trying tried good great nice sure right actually probably pretty little much many few around again already even ever never always often sometimes today tonight tomorrow yesterday different together interesting going everything current".split())
def ld(p,d):return json.loads(p.read_text()) if p.exists() else d
def sv(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+"\n")
def sd(*x):return int(hashlib.sha256(":".join(map(str,x)).encode()).hexdigest()[:16],16)&0x7fffffff
def rr(*x):return random.Random(sd(*x))
def cl(x,a=0,b=1):return max(a,min(b,float(x)))
def wd(t):
 o=[]
 for w in re.findall(r"[a-z][a-z'-]{2,}",str(t or "").lower()):
  w=w.strip("'-")
  if w not in STOP and w not in {n.lower() for n in N.values()} and w not in o:o.append(w)
 return o
def init():
 D.mkdir(exist_ok=True)
 if not(D/"conversation.json").exists():
  s=R/"society"/"conversation.json";(D/"conversation.json").write_text(s.read_text() if s.exists() else "[]\n")
 if not(D/"discourse.json").exists():sv(D/"discourse.json",{"nodes":[],"roots":[]})
 if not(D/"state.json").exists():sv(D/"state.json",{"version":"room-cognition-v2","cycle":0,"last_speaker":None,"silence_cycles":0})
 if not(D/"cognitive_state.json").exists():
  E={}
  for e in O:E[e]={"fast":{"activation":.2,"attention":[]},"medium":{"topics":[]},"slow":{"social_energy":.55,"association":.5},"very_slow":{"identity":1},"noise":{"a":0,"x":0,"i":0,"s":0},"room_memories":[],"self_history":[],"last_event":None,"spoken":0,"silences":0,"people":{p:{"familiarity":.02,"reports":[]} for p in O if p!=e}}
  sv(D/"cognitive_state.json",{"entities":E})
init()
def cv():return ld(D/"conversation.json",[])
def msgs():return[m for m in cv() if m.get("runtime")=="room-cognition-v2"]
def ev():return msgs()[-1] if msgs() else None
def st():return ld(D/"state.json",{})
def cs():return ld(D/"cognitive_state.json",{"entities":{}})
def ds():return ld(D/"discourse.json",{"nodes":[],"roots":[]})
def ni(n):e=O[n//3];z=n%3;role,t=A["roles"][str(z)];return e,z,role,t
def tr(e,k,d=.5):return float(Q[e]["traits"].get(k,d))
def tg(m):
 if not m:return None
 if (m.get("cognition")or{}).get("target"):return m["cognition"]["target"]
 z=m.get("text","").lower()
 for e,n in N.items():
  if e!=m.get("speaker") and re.search(rf"\b{re.escape(n.lower())}\b",z):return e
def dq(e,m):return bool(m and m.get("speaker")!=e and m.get("text","").rstrip().endswith("?") and tg(m) in(None,e))
def mem(e,q,k):
 z=set(q);a=sorted(M[e],key=lambda m:len(set(m["tags"])&z)*2+.5*m["sal"]+.25*m["emo"],reverse=True)
 return a[0] if z and set(a[0]["tags"])&z else rr("m",e,k).choice(sorted(M[e],key=lambda m:m["sal"],reverse=True)[:6])
def nz(e,x,k):
 r=rr("n",e,k);o={}
 for a,s in(("a",.08),("x",.09),("i",.07),("s",.08)):o[a]=round(cl(.82*x["noise"].get(a,0)+r.gauss(0,s),-.25,.25),4)
 return o
def sense(n,k):
 e,z,role,t=ni(n);m=ev();x=cs()["entities"][e];q=wd((m or{}).get("text",""))[:8];mm=mem(e,q,k);u=nz(e,x,k);r=rr("f",k,n)
 if role=="comprehension":
  head=(re.findall(r"[a-z']+",(m or{}).get("text","").lower())or[""])[0];pred={"why":"cause","how":"process","where":"place","when":"time","who":"person","what":"explanation"}.get(head)
  work={t[0]:[{"concept":w,"activation":round(.7+.2*tr(e,"curiosity"),3)}for w in q],t[1]:{"kind":"utterance","clauses":[{"tokens":wd(c)}for c in re.split(r"[,;!?]|\s+(?:but|because|and)\s+",(m or{}).get("text",""))if c.strip()][:6]},t[2]:{"scope":"constituent","expected":pred},t[3]:{"speaker":(m or{}).get("speaker"),"target":tg(m),"reported":q}};ready=.1;att=cl(.4+.3*tr(e,"social_sensitivity")+(.15 if m else-.1)+r.gauss(0,.04))
 elif role=="thought":
  work={t[0]:{"concepts":q+mm["tags"][:4],"breadth":round(cl(tr(e,"openness")+u["x"]),3)},t[1]:{"kind":"merge","event":q,"memory":mm["tags"]},t[2]:mm,t[3]:{"arousal":round(cl(.15+.4*tr(e,"emotional_reactivity")+.2*mm["emo"]),3),"traits":Q[e]["traits"]}};ready=.2+.1*tr(e,"self_disclosure");att=cl(.32+.35*tr(e,"curiosity")+r.gauss(0,.05))
 else:
  yes=dq(e,m);ready=cl(.2+.26*tr(e,"extraversion")+.24*tr(e,"curiosity")+.18*tr(e,"self_disclosure")-.23*tr(e,"inhibition")+(.46 if yes else 0)-(.3 if m and m.get("speaker")==e else 0)+u["s"]-.45*u["i"]+r.gauss(0,.04));att=cl(.3+.25*tr(e,"social_sensitivity")+(.2 if yes else 0));work={t[0]:{"direct_question":yes},t[1]:{"moves":["answer"]if yes else["follow_up","self_disclosure","reaction","new_root"]},t[2]:{"readiness":ready,"surface":None},t[3]:{"silence":True}}
 return{"phase":"sense","node":n,"entity":e,"local":z,"role":role,"tasks":t,"private":{"event":m,"keywords":q,"memory":mm,"noise":u,"work":work},"public":{"node":n,"entity":e,"role":role,"attention":round(att,3),"readiness":round(ready,3)}}
def bus(ps,k):
 if {p["node"]for p in ps}!=set(range(12)):raise RuntimeError("need all 12")
 return{"key":k,"public":[p["public"]for p in sorted(ps,key=lambda x:x["node"])],"private":{e:[p for p in ps if p["entity"]==e]for e in O}}
def rp(b,e,r):return next(p for p in b["private"][e]if p["role"]==r)
def qp(e,m,k):
 z=(m or{}).get("text","").lower()
 if any(a in z for a in("mother","father","sister","brother","friend","cousin","coworker","partner")):a=["Were you close?","What were they like?","How did you two know each other?"]
 elif any(a in z for a in("city","town","house","apartment","school","ocean","mountain","place")):a=["What was that place like?","Do you miss anything about it?","What do you remember most about being there?"]
 elif any(a in z for a in("felt","afraid","angry","sad","happy","love","hated","miss")):a=["How did that affect you?","Did that bother you at the time?","Do you still feel that way?"]
 else:a=["What happened after that?","How did that happen?","Has that changed much since then?"]
 return rr("q",e,k,*wd(z)).choice(a)
def recur(n,k,b):
 e,z,role,t=ni(n);c=rp(b,e,"comprehension");h=rp(b,e,"thought");x=rp(b,e,"expression");m=c["private"]["event"];mm=h["private"]["memory"];r=rr("r",k,n)
 if role=="comprehension":work={t[0]:{"coactive":list(dict.fromkeys(c["private"]["keywords"]+mm["tags"]))[:10]},t[1]:c["private"]["work"][t[1]],t[2]:c["private"]["work"][t[2]],t[3]:{"common_ground":c["private"]["keywords"],"memory_link":mm["id"]}};ready=0
 elif role=="thought":work={t[0]:{"concepts":list(dict.fromkeys(c["private"]["keywords"]+mm["tags"]))[:10]},t[1]:h["private"]["work"][t[1]],t[2]:mm,t[3]:h["private"]["work"][t[3]]};ready=.2
 else:
  ready=cl(x["public"]["readiness"]+r.gauss(0,.025))
  if dq(e,m):move="answer"
  elif not m:move="self_disclosure"
  else:
   w={"follow_up":.32+.33*tr(e,"curiosity"),"self_disclosure":.18+.42*tr(e,"self_disclosure"),"reaction":.2+.22*tr(e,"agreeableness"),"new_root":.08+.38*tr(e,"novelty_seeking")};v=r.random()*sum(w.values());s=0;move="reaction"
   for a,bv in w.items():
    s+=bv
    if v<=s:move=a;break
  use=mm if move!="answer"or set(mm["tags"])&set(wd((m or{}).get("text","")))else None
  plan={"move":move,"target":(m or{}).get("speaker")if move in("answer","follow_up","reaction")else None,"memory":(use or{}).get("id"),"first":(use or{}).get("first"),"concepts":(use or{}).get("tags",c["private"]["keywords"])[:6],"question":qp(e,m,k)if move=="follow_up"else None,"readiness":round(ready,3),"parent":(m or{}).get("discourse_id")}
  plan["latency"]=round(max(.05,1.55-1.15*ready+.35*tr(e,"inhibition")+r.uniform(0,.22)+(.55 if m and m.get("speaker")==e else 0)),4);work={t[0]:{"intent":move},t[1]:plan,t[2]:{"readiness":ready,"latency":plan["latency"]},t[3]:{"provenance":True,"silence":True}}
 return{"phase":"recurrent","node":n,"entity":e,"local":z,"role":role,"tasks":t,"private":{"work":work,"intent":work[t[1]]if role=="expression"else None},"public":{"node":n,"entity":e,"role":role,"readiness":round(ready,3)}}
def fm(e,i):return next((m for m in M[e]if m["id"]==i),None)
def surface(e,i,m,k):
 r=rr("s",e,k,i["move"]);mm=fm(e,i.get("memory"))
 if i["move"]=="follow_up":return i["question"],"structured"
 if i["move"]=="answer":
  if mm:return r.choice(["I ","Actually, I ","Yeah — I "])+mm["first"].rstrip(".")+".","memory"
  h=(re.findall(r"[a-z']+",(m or{}).get("text","").lower())or[""])[0];return(r.choice(["I don't really remember that part.","I'm not sure about that detail."])if h in{"why","how","where","when","who","what"}else r.choice(["Not really.","I don't think so.","I'm not sure."])),"grounded"
 if i["move"]in("self_disclosure","new_root")and mm:return r.choice(["I ","That reminds me that I ","Randomly, I "])+mm["first"].rstrip(".")+".","memory"
 return r.choice(["That part caught my attention.","I can see why that would stick with you.","I hadn't thought about it that way."]),"structured"
def depth(i,d):
 mp={n["id"]:n for n in d["nodes"]};s=set();z=0
 while i and i in mp and i not in s and z<20:s.add(i);z+=1;i=mp[i].get("parent")
 return z
def commit(ps,k):
 S=st();X=cs();Dsc=ds();V=cv();m=ev()
 for e in O:
  x=X["entities"][e];ep=[p for p in ps if p["entity"]==e];x["noise"]=nz(e,x,k);c=next(p for p in ep if p["role"]=="comprehension");x["fast"]["activation"]=round(sum(p["public"]["readiness"]for p in ep)/3,3);x["fast"]["attention"]=c["private"]["work"][c["tasks"][0]]["coactive"][:8];x["medium"]["topics"]=x["fast"]["attention"]
  if m and x["last_event"]!=m["id"]:
   sp=m["speaker"]
   if sp!=e:x["people"][sp]["familiarity"]=round(cl(x["people"][sp]["familiarity"]+.018),3);x["people"][sp]["reports"].append({"source":m["id"],"status":"reported","text":m["text"][:300]});x["people"][sp]["reports"]=x["people"][sp]["reports"][-60:];x["room_memories"].append({"source":m["id"],"status":"observed","speaker":sp,"text":m["text"][:300]});x["room_memories"]=x["room_memories"][-120:]
   x["last_event"]=m["id"]
 q=sorted([(p["private"]["intent"]["latency"],O.index(p["entity"]),p)for p in ps if p["role"]=="expression"and p["private"]["intent"]["readiness"]>=.48],key=lambda x:(x[0],x[1]));spoken=None;stamp=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
 if q:
  p=q[0][2];e=p["entity"];i=p["private"]["intent"];text,mode=surface(e,i,m,k);mid=f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{e}-v2";parent=i.get("parent");der=None
  if i["move"]=="new_root"or(parent and depth(parent,Dsc)>=A["discourse"]["max_depth"]):der=parent;parent=None
  did="d-"+mid;z={"id":mid,"at":stamp,"speaker":e,"text":text,"runtime":"room-cognition-v2","cognition":{"move_type":i["move"],"target":i.get("target"),"memory_provenance":i.get("memory"),"externalization":mode,"compute_nodes":[n+1 for n in A["entities"][e]],"processes":12},"discourse_id":did,"parent_discourse_id":parent,"derived_from":der};V.append(z);Dsc["nodes"].append({"id":did,"speaker":e,"parent":parent,"derived_from":der,"move":i["move"],"target":i.get("target"),"text":text,"at":stamp});Dsc["nodes"]=Dsc["nodes"][-600:];Dsc["roots"]+=([did]if not parent else[]);X["entities"][e]["spoken"]+=1;S["last_speaker"]=e;S["silence_cycles"]=0;spoken=z
 if not spoken:S["silence_cycles"]=S.get("silence_cycles",0)+1;[X["entities"][e].__setitem__("silences",X["entities"][e]["silences"]+1)for e in O]
 S.update({"version":"room-cognition-v2","cycle":S.get("cycle",0)+1,"last_run":stamp,"messages":len(V),"last_public_event":spoken["id"]if spoken else(m or{}).get("id"),"note":"12 nodes x 4 tasks; all four entities process each cycle; no voting"});V=V[-520:];sv(D/"conversation.json",V);sv(D/"discourse.json",Dsc);sv(D/"cognitive_state.json",X);sv(D/"state.json",S)
 minds={"schema":2,"entities":{e:{"name":N[e],"profile":Q[e],"genome":Q[e]["traits"],"development":{"turns":S["cycle"],"spoken":X["entities"][e]["spoken"],"silences":X["entities"][e]["silences"],"response_length_ema":0,"topic_weights":{t:1 for t in X["entities"][e]["medium"]["topics"]},"relationships":{p:v["familiarity"]for p,v in X["entities"][e]["people"].items()},"lifetime_memory_count":len(M[e])},"memory":[{"text":z["text"]}for z in X["entities"][e]["room_memories"][-8:]]}for e in O}}
 L={"generated_at":stamp,"architecture_version":"room-cognition-v2","minds":minds,"profiles":Q,"state":S,"conversation":V,"discourse":Dsc,"network":{"compute_nodes":12,"entities":4,"nodes_per_entity":3,"tasks_per_node":4,"active_processes":48,"voting":False}};sv(D/"live.json",L);sv(R/"society"/"live.json",L);print(N[spoken["speaker"]]+": "+spoken["cognition"]["move_type"]if spoken else"Room silent; all 12 nodes processed")
def test():
 s=[sense(n,"t")for n in range(12)];b=bus(s,"t");r=[recur(n,"t",b)for n in range(12)];assert len(r)==12 and all(len(b["private"][e])==3 for e in O)and A["network"]["voting"]is False and all(len({t for m in M[e]for t in m["types"]})>=10 for e in O);print("PASS 4 entities x 3 nodes x 4 tasks = 48 processes; 12-node bus; bounded discourse; no voting")
def main():
 a=argparse.ArgumentParser();s=a.add_subparsers(dest="c",required=True);n=s.add_parser("node");n.add_argument("--phase",choices=["sense","recurrent"],required=True);n.add_argument("--bus",default="");s.add_parser("bus");s.add_parser("commit");s.add_parser("selftest");x=a.parse_args();k=os.environ.get("ROOM_CYCLE_KEY")or f"{st().get('cycle',0)+1}:{os.environ.get('GITHUB_RUN_ID','local')}"
 if x.c=="node":i=int(os.environ["ROOM_NODE_ID"]);z=sense(i,k)if x.phase=="sense"else recur(i,k,ld(Path(x.bus),{}));P.mkdir(exist_ok=True);sv(P/f"{x.phase}-{i:02d}.json",z)
 elif x.c=="bus":W.mkdir(exist_ok=True);sv(W/"bus-sense.json",bus([ld(p,{})for p in sorted(P.glob("sense-*.json"))],k))
 elif x.c=="commit":
  z=[ld(p,{})for p in sorted(P.glob("recurrent-*.json"))];assert {p["node"]for p in z}==set(range(12));commit(z,k)
 else:test()
if __name__=="__main__":main()
