#!/usr/bin/env python3
import hashlib, json, random, re, urllib.parse, urllib.request

UA = 'Things-Universe-Shared-Cluster/2.0 (+https://github.com/maaronfanberg-lab/me-)'
GENERIC = {
    'thing','things','object','objects','entity','entities','concept','concepts','system','systems',
    'process','processes','subject','subjects','topic','topics','stuff','something','phenomenon','phenomena',
    'category','categories','item','items','property','properties','type','types','kind','kinds'
}
DROP_CAT = re.compile(r'\b(wikipedia|articles|pages|templates|stubs?|lists?|by year|by country|births|deaths|works by|albums by|songs by|films by|people from|members of|redirects|tracking|maintenance)\b', re.I)
DESCRIPTION_CUT = re.compile(r'\s+(?:by|from|in|at|directed by|written by|created by|founded by)\s+', re.I)
LEADING_ARTICLE = re.compile(r'^(?:the|a|an)\s+', re.I)

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
    'literary work': [('literature','is a form of'),('narrative','can contain'),('language','uses'),('meaning','can convey')],
    'literature': [('language','uses'),('narrative','often uses'),('meaning','conveys'),('culture','is part of'),('art','is a form of')],
    "children's book": [("children's literature",'is a kind of'),('literature','is a kind of'),('narrative','often uses'),('play','can use')],
    "children's literature": [('literature','is a kind of'),('education','can support'),('narrative','often uses'),('play','can use'),('imagination','can cultivate')],
    'picture book': [("children's literature",'is a kind of'),('visual art','combines with text'),('narrative','often presents')],
    'book': [('literary work','can be a'),('literature','can be a form of'),('language','uses')],
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
    'IsA': ('is a kind of','includes'), 'PartOf': ('is part of','contains'), 'HasA': ('has','is part of'),
    'UsedFor': ('is used for','can use'), 'CapableOf': ('can','can be done by'), 'Causes': ('can cause','can result from'),
    'HasProperty': ('has property','is a property of'), 'RelatedTo': ('is related to','is related to'),
    'Synonym': ('is synonymous with','is synonymous with'), 'Antonym': ('is opposed to','is opposed to'),
    'DerivedFrom': ('is derived from','can give rise to'), 'FormOf': ('is a form of','has form'),
    'MotivatedByGoal': ('can be motivated by','can motivate'), 'CausesDesire': ('can create desire for','can be desired because of'),
    'HasPrerequisite': ('requires','can enable'), 'HasSubevent': ('can include','can be part of'),
    'MannerOf': ('is a manner of','can be expressed as'), 'SimilarTo': ('is similar to','is similar to'),
    'DistinctFrom': ('is distinct from','is distinct from'),
}

WD_PROPS = {
    'P31': ('is an instance of','has instance'), 'P279': ('is a subclass of','has subclass'),
    'P136': ('has genre','is genre of'), 'P921': ('has main subject','is main subject of'),
    'P361': ('is part of','contains'), 'P527': ('has part','is part of'),
    'P1269': ('is a facet of','has facet'), 'P1552': ('has characteristic','characterizes'),
}


def key(s):
    return re.sub(r'\s+', ' ', str(s or '').strip().lower())


def sense_key(s):
    return LEADING_ARTICLE.sub('', key(s))


def cap(s):
    s=' '.join(str(s or '').split())
    return s[:1].upper()+s[1:] if s else s


def fetch_json(url, timeout=4.5):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8','replace'))
    except Exception:
        return None


def edge(label, rel, rev, score, source):
    return {'k':key(label),'label':cap(label),'rel':rel,'rev':rev,'score':float(score),'source':source}


def atlas(term):
    out=[]; t=key(term)
    for label,rel in ATLAS.get(t,[]):out.append(edge(label,rel,'is conceptually linked to',340,'conceptual bridge atlas'))
    for src,rows in ATLAS.items():
        for label,_ in rows:
            if key(label)==t:out.append(edge(src,'is conceptually linked to','is conceptually linked to',290,'conceptual bridge atlas'))
    return out


def conceptnet(term, limit=60):
    t=key(term); node='/c/en/'+urllib.parse.quote(t.replace(' ','_'))
    j=fetch_json('https://api.conceptnet.io/query?node='+node+'&limit='+str(limit)); out=[]
    for e in (j or {}).get('edges',[]):
        rn=str((e.get('rel') or {}).get('@id','')).split('/')[-1]
        if rn not in REL:continue
        st=e.get('start') or {}; en=e.get('end') or {}; sk=key(st.get('label')); ek=key(en.get('label'))
        forward=sk==t
        if not forward and ek!=t:continue
        other=en if forward else st; oid=str(other.get('@id','')); lab=other.get('label')
        if not oid.startswith('/c/en/') or not lab or len(str(lab))>70:continue
        ok=key(lab)
        if not ok or ok==t:continue
        rel,rev=REL[rn]
        if not forward:rel,rev=rev,rel
        weight=float(e.get('weight') or 1.0)
        out.append(edge(lab,rel,rev,215+min(50,weight*12),'ConceptNet'))
    return out


def wikipedia_identity(term):
    url=('https://en.wikipedia.org/w/api.php?origin=*&action=query&format=json&redirects=1&'
         'prop=pageprops|categories&cllimit=60&titles='+urllib.parse.quote(term))
    j=fetch_json(url); pages=list((((j or {}).get('query') or {}).get('pages') or {}).values())
    if not pages:return None
    p=pages[0]
    if 'missing' in p:return None
    cats=[]
    for c in p.get('categories',[]):
        lab=str(c.get('title','')).replace('Category:','').strip()
        if lab and len(lab)<=75 and not DROP_CAT.search(lab):cats.append(lab)
    return {'title':p.get('title') or term,'qid':(p.get('pageprops') or {}).get('wikibase_item'),'categories':cats}


def wikidata_search_qid(term):
    q=urllib.parse.quote(term)
    j=fetch_json('https://www.wikidata.org/w/api.php?origin=*&action=wbsearchentities&format=json&language=en&type=item&limit=8&search='+q)
    hits=(j or {}).get('search',[])
    if not hits:return None
    sk=sense_key(term)
    exact=[h for h in hits if sense_key(h.get('label'))==sk]
    return (exact[0] if exact else hits[0]).get('id')


def wikidata_edges(qid, term):
    if not qid:return[]
    url='https://www.wikidata.org/w/api.php?origin=*&action=wbgetentities&format=json&languages=en&props=claims|descriptions&ids='+urllib.parse.quote(qid)
    j=fetch_json(url); ent=((j or {}).get('entities') or {}).get(qid) or {}; claims=ent.get('claims') or {}; refs=[]
    for prop,(rel,rev) in WD_PROPS.items():
        for c in (claims.get(prop) or [])[:12]:
            v=(((c.get('mainsnak') or {}).get('datavalue') or {}).get('value') or {})
            if isinstance(v,dict) and v.get('id'):refs.append((v['id'],rel,rev))
    ids=[]
    for q,_,_ in refs:
        if q not in ids:ids.append(q)
    labels={}
    if ids:
        url='https://www.wikidata.org/w/api.php?origin=*&action=wbgetentities&format=json&languages=en&props=labels&ids='+urllib.parse.quote('|'.join(ids),safe='|')
        lj=fetch_json(url)
        for q,e in ((lj or {}).get('entities') or {}).items():
            lab=(((e or {}).get('labels') or {}).get('en') or {}).get('value')
            if lab:labels[q]=lab
    out=[]; t=key(term)
    for q,rel,rev in refs:
        lab=labels.get(q)
        if lab and key(lab)!=t and len(lab)<=70:out.append(edge(lab,rel,rev,320,'Wikidata'))
    desc=(((ent.get('descriptions') or {}).get('en') or {}).get('value') or '').strip()
    if desc:
        phrase=DESCRIPTION_CUT.split(desc,1)[0].strip(' .,:;()')
        phrase=re.sub(r'^\d{4}\s+','',phrase)
        if 2<=len(phrase)<=55 and key(phrase)!=t:
            out.append(edge(phrase,'is described as','can describe',305,'Wikidata description'))
    return out


def category_abstractions(categories):
    out=[]; seen=set()
    for cat in categories:
        c=key(cat); choices=[]
        if "children's book" in c or 'childrens book' in c:choices=["children's literature"]
        elif re.search(r'\bbooks?\b',c):choices=['literature']
        elif re.search(r'\bnovels?\b',c):choices=['literature']
        elif re.search(r'\bpoetry|poems?\b',c):choices=['poetry','literature']
        elif re.search(r'\bfilms?|movies?\b',c):choices=['film','art']
        elif re.search(r'\bsongs?\b',c):choices=['music']
        elif re.search(r'\bvideo games?\b',c):choices=['game']
        for lab in choices:
            if lab not in seen:
                seen.add(lab);out.append(edge(lab,'belongs to conceptual field','conceptual field includes',250,'Wikipedia category abstraction'))
    return out


def root_knowledge(term):
    ident=wikipedia_identity(term); out=[]
    if ident:
        qid=ident.get('qid') or wikidata_search_qid(ident.get('title') or term)
        out.extend(wikidata_edges(qid,term));out.extend(category_abstractions(ident.get('categories') or []))
    else:
        out.extend(wikidata_edges(wikidata_search_qid(term),term))
    return out


def merge_edges(groups):
    best={}
    for group in groups:
        for e in group:
            if not e.get('k'):continue
            old=best.get(e['k'])
            if old is None or e['score']>old['score']:best[e['k']]=e
    return list(best.values())


def lens_score(e,lens_words,depth,jitter=0):
    s=e['score']-depth*18; text=key(e['label'])+' '+key(e['rel'])
    if e['k'] in GENERIC:s-=170
    if len(e['k'])<=2:s-=80
    if lens_words and any(w in text for w in lens_words):s+=48
    if e['source']=='Wikidata':s+=24
    if e['source']=='Wikidata description':s+=14
    if e['source']=='ConceptNet':s+=10
    return s+jitter


def expand(term,is_root,lens_words,rng,cache):
    ck=(key(term),bool(is_root))
    if ck in cache:return cache[ck]
    groups=[atlas(term),conceptnet(term,65 if is_root else 45)]
    if is_root:groups.append(root_knowledge(term))
    rows=merge_edges(groups)
    for e in rows:e['_j']=rng.uniform(-6,6)
    rows.sort(key=lambda e:lens_score(e,lens_words,0,e['_j']),reverse=True)
    cache[ck]=rows
    return rows


def reconstruct(meet,left,right,labels):
    nodes=[];cur=meet
    while cur is not None:
        nodes.append(cur);cur=left[cur]['parent'] if cur in left else None
    nodes.reverse();edges=[]
    for i in range(len(nodes)-1):
        rec=left[nodes[i+1]];edges.append({'a':labels[nodes[i]],'b':labels[nodes[i+1]],'rel':rec['edge']['rel'],'source':rec['edge']['source']})
    cur=meet
    while cur in right and right[cur]['parent'] is not None:
        rec=right[cur];parent=rec['parent'];edges.append({'a':labels[cur],'b':labels[parent],'rel':rec['edge']['rev'],'source':rec['edge']['source']});cur=parent
    return edges


def path_score(edges,left_score,right_score):
    if not edges:return -9999
    p=0
    for e in edges:
        if key(e['a']) in GENERIC or key(e['b']) in GENERIC:p+=130
        if e['source']=='Wikipedia category abstraction':p+=12
    avg=(left_score+right_score)/max(1,len(edges))
    return round(avg-len(edges)*38-p,3)


def deterministic_rng(a,b,worker):
    h=hashlib.sha256((key(a)+'|'+key(b)+'|'+str(worker)).encode()).digest()
    return random.Random(int.from_bytes(h[:8],'big'))


def search_pair(a,b,worker,max_depth=6):
    lens_name,lens_words=LENSES[worker%len(LENSES)];rng=deterministic_rng(a,b,worker);cache={}
    ka,kb=key(a),key(b);labels={ka:cap(a),kb:cap(b)}
    if ka==kb:return {'from':a,'to':b,'edges':[],'score':10000,'lens':lens_name,'expanded':0}
    left={ka:{'parent':None,'edge':None,'score':0.0,'depth':0}};right={kb:{'parent':None,'edge':None,'score':0.0,'depth':0}}
    front_l=[ka];front_r=[kb];expanded=0;best=None;beam=5+(worker%3);branch=12+(worker%4)*2;limit=44
    for _wave in range(max_depth):
        for own,other,front_name in ((left,right,'L'),(right,left,'R')):
            front=front_l if front_name=='L' else front_r;next_rows=[]
            for cur in sorted(front,key=lambda k:own[k]['score'],reverse=True)[:beam]:
                if expanded>=limit:break
                rec=own[cur]
                if rec['depth']>=max_depth-1:continue
                rows=expand(labels.get(cur,cur),rec['depth']==0,lens_words,rng,cache)[:branch];expanded+=1
                for e in rows:
                    nk=e['k'];labels.setdefault(nk,e['label']);nd=rec['depth']+1
                    ns=rec['score']+lens_score(e,lens_words,nd,e.get('_j',0));old=own.get(nk)
                    if old is None or ns>old['score']:
                        own[nk]={'parent':cur,'edge':e,'score':ns,'depth':nd};next_rows.append(nk)
                    hit=other.get(nk)
                    if hit and nd+hit['depth']<=max_depth:
                        edges=reconstruct(nk,left,right,labels)
                        lscore=left.get(nk,{}).get('score',ns if front_name=='L' else hit['score'])
                        rscore=right.get(nk,{}).get('score',ns if front_name=='R' else hit['score'])
                        score=path_score(edges,lscore,rscore)
                        cand={'from':a,'to':b,'edges':edges,'score':score,'lens':lens_name,'expanded':expanded}
                        if edges and (best is None or score>best['score']):best=cand
            unique=[];seen=set()
            for k in sorted(next_rows,key=lambda k:own[k]['score'],reverse=True):
                if k not in seen:seen.add(k);unique.append(k)
            if front_name=='L':front_l=unique[:beam*2]
            else:front_r=unique[:beam*2]
            if best and len(best['edges'])<=4:return best
            if expanded>=limit:break
        if expanded>=limit or (not front_l and not front_r):break
    return best or {'from':a,'to':b,'edges':[],'score':-9999,'lens':lens_name,'expanded':expanded}


def worker_result(request,worker):
    terms=request['payload']['terms'];pairs=[]
    for i in range(len(terms)):
        for j in range(i+1,len(terms)):pairs.append((terms[i],terms[j]))
    a,b=pairs[worker%len(pairs)];path=search_pair(a,b,worker,request['payload'].get('max_depth',6))
    return {'project':'discovery','task':'conceptual_bridge','job_id':request['job_id'],'terms':terms,'pair':[a,b],'path':path,'strategy':path.get('lens'),'units':path.get('expanded',0)}
