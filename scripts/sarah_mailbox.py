import json, os, urllib.request

repo = os.environ['GITHUB_REPOSITORY']
token = os.environ['GITHUB_TOKEN']
event_path = os.environ['GITHUB_EVENT_PATH']
model = os.environ.get('SARAH_MODEL','qwen2.5:1.5b')

with open(event_path,'r',encoding='utf-8') as f:
    event = json.load(f)

issue = event.get('issue') or {}
comment = event.get('comment') or {}
number = issue.get('number')
body = (comment.get('body') or '').strip()
user = (comment.get('user') or {}).get('login','unknown')

if not number or not body:
    raise SystemExit('No issue comment to answer')
if issue.get('title') != 'Sarah — conversation room':
    raise SystemExit('Not Sarah room')
if user in {'github-actions[bot]','supercomputer-bot'}:
    raise SystemExit('Ignoring bot comment')

headers = {
    'Authorization': f'Bearer {token}',
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'sarah-mailbox'
}

def gh_json(url, method='GET', data=None):
    req = urllib.request.Request(url, method=method, headers=headers)
    if data is not None:
        raw = json.dumps(data).encode('utf-8')
        req.data = raw
        req.add_header('Content-Type','application/json')
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode('utf-8'))

comments = gh_json(f'https://api.github.com/repos/{repo}/issues/{number}/comments?per_page=100')
with open('sarah/core.txt','r',encoding='utf-8') as f:
    system = f.read().strip()

messages = [{'role':'system','content':system}]
for c in comments[-24:]:
    author = (c.get('user') or {}).get('login','')
    text = (c.get('body') or '').strip()
    if not text:
        continue
    if author == 'github-actions[bot]':
        # Strip the visible signature added by the workflow.
        if text.startswith('**Sarah:**'):
            text = text[len('**Sarah:**'):].strip()
        messages.append({'role':'assistant','content':text})
    else:
        messages.append({'role':'user','content':text})

payload = json.dumps({
    'model': model,
    'messages': messages,
    'stream': False,
    'options': {'temperature': 0.9, 'top_p': 0.9, 'num_predict': 700}
}).encode('utf-8')
req = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=payload, headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req, timeout=900) as r:
    out = json.loads(r.read().decode('utf-8'))
reply = ((out.get('message') or {}).get('content') or '').strip()
if not reply:
    reply = "I seem to have woken without a sentence. That's mildly embarrassing."

# Keep Sarah's response readable and avoid accidentally posting gigantic model output.
reply = reply[:12000]
gh_json(f'https://api.github.com/repos/{repo}/issues/{number}/comments', 'POST', {'body': '**Sarah:**\n\n' + reply})
print('Sarah replied.')
