#!/usr/bin/env python3
import glob, json, os, time
parts=[]
for p in sorted(glob.glob('cluster_parts/worker-*.json')):
    with open(p) as f: parts.append(json.load(f))
if not parts: raise SystemExit('no worker results')
workload=parts[0]['workload']
summary={
  'generated_at': int(time.time()),
  'workload': workload,
  'workers': len(parts),
  'scale': parts[0]['scale'],
  'total_units': sum(p['units'] for p in parts),
  'slowest_worker_seconds': max(p['elapsed'] for p in parts),
  'aggregate_rate': sum(p['rate'] for p in parts),
  'parts': parts,
}
if workload=='montecarlo':
    samples=sum(p['result']['samples'] for p in parts)
    inside=sum(p['result']['inside'] for p in parts)
    summary['result']={'pi_estimate':4*inside/samples,'samples':samples}
elif workload=='primes':
    summary['result']={'prime_count':sum(p['result']['count'] for p in parts),'largest_prime':max(p['result']['last_prime'] for p in parts)}
elif workload=='hashstorm':
    summary['result']={'combined_digest':'-'.join(p['result']['digest'][:12] for p in parts)}
os.makedirs('cluster', exist_ok=True)
with open('cluster/latest.json','w') as f: json.dump(summary,f,indent=2)
print(json.dumps(summary,indent=2))
