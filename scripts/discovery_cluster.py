#!/usr/bin/env python3
import json, random, re, urllib.parse, urllib.request

UA = 'Things-Universe-Shared-Cluster/1.0 (+https://github.com/maaronfanberg-lab/me-)'
GENERIC = {
    'thing','things','object','objects','entity','entities','concept','concepts','system','systems',
    'process','processes','subject','subjects','topic','topics','stuff','something','phenomenon','phenomena',
    'category','categories','item','items','property','properties','type','types','kind','kinds'
}
DROP_CAT = re.compile(r'\b(wikipedia|articles|pages|templates|stubs?|lists?|by year|by country|births|deaths|works by|albums by|songs by|films by|people from|members of)\b', re.I)

LENSES = [
    ('language', {'language','meaning','word','symbol','communication','story','narrative','literature','text'}),
    ('ethics', {'ethics','moral','morality','value','good','bad','rule','authority','justice','choice'}),
    ('mind', {'mind','thought','emotion','feeling','memory','attention','cognition','belief','perception'}),
    ('culture', {'culture','society','tradition','art','literature','education','play','ritual','history'}),
    ('causal', {'cause','effect','influence','produce','result','change','behavior','action','consequence'}),
    ('structure', {'part','whole','class','category','system','structure','pattern','form','relation'}),
    ('aesthetic', {'art','beauty','style','play','absurdity','humor','imagination','creativity','symbol'}),
    ('knowledge', {'knowledge','reason','reasoning','evidence','truth','belief','learning','inference','philosophy'}),
    ('social', {'social','person','people','trust','relationship','power','authority','norm','community'}),
    ('science', {'science','biology','brain','chemistry','physics','mathematics','neuron','dopamine','nature'}),
    ('function', {'use','purpose','function','goal','tool','support','require','practice','method'}),
    ('wide', set()),
]

ATLAS = {
    'philosophy': [('reasoning','studies and uses'),('knowledge','studies'),('ethics','includes'),('meaning','examines'),('language','examines'),('mind','examines'),('truth','examines')],
    'literature': [('language','uses'),('narrative','often uses'),('meaning','conveys'),('culture','is part of'),('art','is a form of')],
    "children's literature": [('literature','is a kind of'),('education','can support'),('narrative','often uses'),('play','can use'),('imagination','can cultivate')],
    'picture book': [("children's literature",'is a kind of'),('visual art','combines with text'),('narrative','often presents')],
    'narrative': [('story','is closely related to'),('meaning','can convey'),('language','can be expressed through'),('culture','can transmit')],
    'story': [('narrative','is a form of'),('meaning','can convey'),('memory','can organize'),('culture','can transmit')],
    'language': [('meaning','expresses'),('communication','supports'),('symbol','uses'),('thought','can shape')],
    'meaning': [('interpretation','depends on'),('language','can be expressed through'),('philosophy','is examined by')],
    'ethics': [('morality','studies'),('value','examines'),('choice','evaluates'),('consequence','can consider'),('philosophy','is a branch of')],
    'morality': [('ethics','is studied by'),('rule','can involve'),('value','depends on'),('behavior','can guide')],
    'rule': [('authority','can be enforced by'),('behavior','can guide'),('morality','can reflect'),('norm','is related to')],
    'authority': [('power','is related to'),('rule','can enforce'),('social norm','can shape'),('ethics','can be evaluated by')],
    'play': [('imagination','uses'),('learning','can support'),('rule','can involve'),('creativity','supports')],
    'absurdity': [('humor','can produce'),('meaning','can challenge'),('logic','can violate'),('art','can use')],
    'imagination': [('creativity','supports'),('thought','is a form of'),('play','supports'),('narrative','can generate')],
    'art': [('culture','is part of'),('meaning','can convey'),('symbol','can use'),('aesthetics','is studied by')],
    'aesthetics': [('beauty','examines'),('art','examines'),('philosophy','is a branch of')],
    'emotion': [('feeling','is related to'),('brain','involves'),('behavior','can influence'),('memory','can influence')],
    'love': [('emotion','is a kind of'),('attachment','can involve'),('trust','can involve'),('dopamine','can involve')],
    'fear': [('emotion','is a kind of'),('threat','can respond to'),('brain','involves'),('behavior','can influence')],
    'peace': [('conflict','is opposed to'),('trust','can depend on'),('cooperation','can support'),('justice','can support')],
    'dopamine': [('neurotransmitter','is a kind of'),('brain','acts in'),('motivation','can influence'),('reward','is involved in')],
    'neurotransmitter': [('brain','acts in'),('neuron','is released by'),('chemical signaling','supports')],
    'brain': [('mind','supports'),('cognition','supports'),('emotion','supports'),('neuron','contains')],
    'memory': [('learning','supports'),('brain','depends on'),('meaning','can organize'),('identity','can influence')],
    'trust': [('relationship','supports'),('social interaction','affects'),('cooperation','supports'),('risk','can involve')],
    'music': [('sound','uses'),('rhythm','uses'),('emotion','can evoke'),('mathematics','can relate to'),('art','is a form of')],
    'mathematics': [('pattern','studies'),('reasoning','uses'),('number','studies'),('structure','studies')],
    'fungus': [('organism','is a kind of'),('ecosystem','participates in'),('decomposition','can perform'),('symbiosis','can form')],
    'economics': [('scarcity','studies'),('choice','studies'),('value','studies'),('resource','studies'),('social science','is a kind of')],
}

REL = {
    'IsA': ('is a kind of','includes'),
    'PartOf': ('is part of','contains'),
    'HasA': ('has','is part of'),
    'UsedFor': ('is used for','can use'),
    'CapableOf': ('can','can be done by'),
    'Causes': ('can cause','can result from'),
    'HasProperty': ('has property','is a property of'),
    'RelatedTo': ('is related to','is related to'),
    'Synonym': ('is synonymous with','is synonymous with'),
    'Antonym': ('is opposed to','is opposed to'),
    'DerivedFrom': ('is derived from','can give rise to'),
    'FormOf': ('is a form of','has form'),
    'MotivatedByGoal': ('can be motivated by','can motivate'),
    'CausesDesire': ('can create desire for','can be desired because of'),
    'HasPrerequisite': ('requires','can enable'),
    'HasSubevent': ('can include','can be part of'),
    'MannerOf': ('is a manner of','can be expressed as'),
    'SimilarTo': ('is similar to','is similar to'),
    'DistinctFrom': ('is distinct from','is distinct from'),
}

WD_PROPS = {
    'P31': ('is an instance of','has instance'),
    'P279': ('is a subclass of','has subclass'),
    'P136': ('has genre','is genre of'),
    'P921': ('has main subject','is main subject of'),
    'P361': ('is part of','contains'),
    'P527': ('has part','is part of'),
    'P1269': ('is a facet of','has facet'),
    'P1552': ('has characteristic','characterizes'),
}


def key(s):
    return re.sub(r'\s+', ' ', str(s or '').strip().lower())


def cap(s):
    s = ' '.join(str(s or '').split())
    return s[:1].upper() + s[1:] if s else s


def fetch_json(url, timeout=4.0):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8','replace'))
    except Exception:
        return None


def edge(k, label, rel, rev, score, source):
    return {'k':key(k),'label':cap(label),'rel':rel,'rev':rev,'score':float(score),'source':source}


def atlas(term):
    out=[]
    for label, rel in ATLAS.get(key(term), []):
        out.append(edge(label,label,rel,'is conceptually linked to',330,'conceptual bridge atlas'))
    t=key(term)
    for src, rows in ATLAS.items():
        for label, rel in rows:
            if key(label)==t:
                out.append(edge(src,src,'is conceptually linked to','is conceptually linked to',285,'conceptual bridge atlas'))
    return out


def conceptnet(term, limit=70):
    node='/c/en/'+urllib.parse.quote(key(term).replace(' ','_'))
    j=fetch_json('https://api.conceptnet.io/query?node='+node+'&limit='+str(limit), 4.5)
    out=[]; t=key(term)
    for e in (j or {}).get('edges',[]):
        rn=str((e.get('rel') or {}).get('@id','')).split('/')[-1]
        if rn not in REL: continue
        st=e.get('start') or {}; en=e.get('end') or {}
        sk=key(st.get('label')); ek=key(en.get('label'))
        forward = sk==t
        if not forward and ek!=t: continue
        other=en if forward else st
        oid=str(other.get('@id',''))
        lab=other.get('label')
        if not oid.startswith('/c/en/') or not lab: continue
        ok=key(lab)
        if not ok or ok==t or len(lab)>70: continue
        rel,rev=REL[rn]
        if not forward: rel,rev=rev,rel
        weight=float(e.get('weight') or 1.0)
        out.append(edge(ok,lab,rel,rev,210+min(45,weight*12),'ConceptNet'))
    return out


def wikidata(term):
    q=urllib.parse.quote(term)
    s=fetch_json('https://www.wikidata.org/w/api.php?origin=*&action=wbsearchentities&format=json&language=en&type=item&limit=6&search='+q, 4.5)
    hits=(s or {}).get('search',[])
    if not hits:return[]
    t=key(term)
    hit=next((h for h in hits if key(h.get('label'))==t),hits[0])
    qid=hit.get('id')
    if not qid:return[]
    e=fetch_json('https://www.wikidata.org/w/api.php?origin=*&action=wbgetentities&format=json&languages=en&props=claims&ids='+qid, 4.5)
    claims=((e or {}).get('entities',{}).get(qid,{}) or {}).get('claims',{})
    refs=[]
    for prop,(rel,rev) in WD_PROPS.items():
        for c in (claims.get(prop) or [])[:10]:
            v=(((c.get('mainsnak') or {}).get('datavalue') or {}).get('value') or {})
            if isinstance(v,dict) and v.get('id'):
                refs.append((v['id'],rel,rev))
    ids=[]
    for qid2,_,_ in refs:
        if qid2 not in ids: ids.append(qid2)
    ids=ids[:40]
    if not ids:return[]
    labels=fetch_json('https://www.wikidata.org/w/api.php?origin=*&action=wbgetentities&format=json&languages=en&props=labels&ids='+urllib.parse.quote('|'.join(ids),safe='|'),4.5)
    ents=(labels or {}).get('entities',{})
    out=[]
    for qid2,rel,rev in refs:
        lab=((ents.get(qid2,{}) or {}).get('labels',{}).get('en',{}) or {}).get('value')
        if lab and key(lab)!=t and len(lab)<=70:
            out.append(edge(lab,lab,rel,rev,300,'Wikidata'))
    return out


def wikipedia_fields(term):
    url='https://en.wikipedia.org/w/api.php?origin=*&action=query&format=json&redirects=1&prop=categories&cllimit=60&titles='+urllib.parse.quote(term)
    j=fetch_json(url,4.5)
    pages=list(((j or {}).get('query') or {}).get('pages',{}).values())
    if not pages:return[]
    page=pages[0]
    if 'missing' in page:return[]
    out=[]; seen=set(); t=key(term)
    for c in page.get('categories',[]):
        lab=str(c.get('title','')).replace('Category:','').strip()
        lab=re.sub(r'\s+by (country|year|century|nationality|language)$','',lab,flags=re.I).strip()
        k=key(lab)
        if not k or k==t or k in seen or len(lab)>65 or DROP_CAT.search(lab):continue
        seen.add(k); out.append(edge(k,lab,'belongs to conceptual field','conceptual field includes',145,'Wikipedia conceptual field'))
        if len(out)>=12:break
    return out


def merge_edges(groups):
    best={}
    for group in groups:
        for e in group:
            if not e['k']:continue
            old=best.get(e['k'])
            if old is None or e['score']>old['score']:best[e['k']]=e
    return list(best.values())


def lens_score(e, lens_words, depth, jitter):
    k=e['k']; lab=key(e['label']); rel=key(e['rel'])
    s=e['score'] - depth*18
    if k in GENERIC: s-=150
    if len(k)<=2:s-=80
    if lens_words and any(w in lab or w in rel for w in lens_words):s+=46
    if e['source']=='ConceptNet':s+=12
    if e['source']=='Wikidata':s+=22
    if 'conceptual field' in rel:s-=22
    return s+jitter


def expand(term, is_root, lens_words, rng, cache):
    ck=(key(term),bool(is_root))
    if ck in cache:return cache[ck]
    groups=[atlas(term),conceptnet(term,70 if is_root else 45)]
    if is_root:
        groups.append(wikidata(term));groups.append(wikipedia_fields(term))
    rows=merge_edges(groups)
    for e in rows:e['_j']=rng.uniform(-7,7)
    rows.sort(key=lambda e:lens_score(e,lens_words,0,e['_j']), reverse=True)
    cache[ck]=rows
    return rows


def reconstruct(meet, left, right, labels):
    left_nodes=[]; cur=meet
    while cur is not None:
        left_nodes.append(cur)
        cur=left[cur]['parent'] if cur in left else None
    left_nodes.reverse()
    edges=[]
    for i in range(len(left_nodes)-1):
        child=left_nodes[i+1]; rec=left[child]
        edges.append({'a':labels[left_nodes[i]],'b':labels[child],'rel':rec['edge']['rel'],'source':rec['edge']['source']})
    cur=meet
    while cur in right and right[cur]['parent'] is not None:
        rec=right[cur]; parent=rec['parent']
        edges.append({'a':labels[cur],'b':labels[parent],'rel':rec['edge']['rev'],'source':rec['edge']['source']})
        cur=parent
    return edges


def path_penalty(edges):
    if not edges:return 9999
    p=max(0,len(edges)-3)*28
    for e in edges:
        if key(e['a']) in GENERIC or key(e['b']) in GENERIC:p+=110
        if 'conceptual field' in key(e['rel']):p+=18
        if e['source']=='conceptual bridge atlas':p+=4
    return p


def search_pair(a,b,worker,max_depth=6):
    lens_name,lens_words=LENSES[worker%len(LENSES)]
    rng=random.Random(99173 + worker*104729 + hash(key(a)+'|'+key(b))%100000)
    cache={}; ka,kb=key(a),key(b)
    labels={ka:cap(a),kb:cap(b)}
    if ka==kb:
        return {'from':a,'to':b,'edges':[],'score':10000,'lens':lens_name,'expanded':0}
    left={ka:{'parent':None,'edge':None,'score':0,'depth':0}}
    right={kb:{'parent':None,'edge':None,'score':0,'depth':0}}
    front_l=[ka];front_r=[kb];expanded=0
    beam=5+(worker%3); branch=11+(worker%4)*2
    best=None
    for turn in range(max_depth):
        side_left = len(front_l)<=len(front_r) if front_l and front_r else bool(front_l)
        if not front_l and not front_r:break
        front=front_l if side_left else front_r
        own=left if side_left else right
        other=right if side_left else left
        next_rows=[]
        for cur in sorted(front,key=lambda k:own[k]['score'],reverse=True)[:beam]:
            rec=own[cur]; root=rec['depth']==0
            rows=expand(labels.get(cur,cur),root,lens_words,rng,cache)[:branch]
            expanded+=1
            for e in rows:
                nk=e['k']; labels.setdefault(nk,e['label'])
                ns=rec['score']+lens_score(e,lens_words,rec['depth']+1,e.get('_j',0))
                old=own.get(nk)
                if old is None or ns>old['score']:
                    own[nk]={'parent':cur,'edge':e,'score':ns,'depth':rec['depth']+1}
                    next_rows.append(nk)
                if nk in other:
                    edges=reconstruct(nk,left,right,labels)
                    score=left[nk]['score']+right[nk]['score']-path_penalty(edges)
                    cand={'from':a,'to':b,'edges':edges,'score':round(score,3),'lens':lens_name,'expanded':expanded}
                    if edges and (best is None or cand['score']>best['score']):best=cand
        if side_left:front_l=list(dict.fromkeys(next_rows))
        else:front_r=list(dict.fromkeys(next_rows))
        if best and len(best['edges'])<=4:break
    return best or {'from':a,'to':b,'edges':[],'score':-9999,'lens':lens_name,'expanded':expanded}


def worker_result(request, worker):
    terms=request['payload']['terms']; pairs=[]
    for i in range(len(terms)):
        for j in range(i+1,len(terms)):pairs.append((terms[i],terms[j]))
    a,b=pairs[worker%len(pairs)]
    path=search_pair(a,b,worker,request['payload'].get('max_depth',6))
    return {
        'project':'discovery','task':'conceptual_bridge','job_id':request['job_id'],
        'terms':terms,'pair':[a,b],'path':path,'strategy':path.get('lens'),
        'units':path.get('expanded',0),
    }
