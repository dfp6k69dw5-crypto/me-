#!/usr/bin/env python3
import json, math, os, random, sys, time, hashlib

worker = int(os.getenv('WORKER_ID','0'))
workers = int(os.getenv('WORKER_COUNT','8'))
workload = os.getenv('WORKLOAD','montecarlo')
scale = max(1, min(20, int(os.getenv('SCALE','5'))))
started = time.time()

if workload == 'montecarlo':
    n = scale * 1_000_000
    rng = random.Random(9173 + worker * 104729)
    inside = 0
    for _ in range(n):
        x, y = rng.random(), rng.random()
        inside += (x*x + y*y <= 1.0)
    result = {'samples': n, 'inside': inside}
    units = n
elif workload == 'primes':
    width = scale * 120_000
    lo = 2 + worker * width
    hi = lo + width
    count = 0
    last = 2
    for n in range(max(2, lo), hi):
        prime = True
        r = int(math.isqrt(n))
        for d in range(2, r + 1):
            if n % d == 0:
                prime = False
                break
        if prime:
            count += 1
            last = n
    result = {'range':[lo,hi], 'count':count, 'last_prime':last}
    units = width
elif workload == 'hashstorm':
    n = scale * 500_000
    seed = f'cluster-{worker}'.encode()
    h = seed
    for i in range(n):
        h = hashlib.sha256(h + i.to_bytes(8,'little')).digest()
    result = {'iterations': n, 'digest': h.hex()}
    units = n
else:
    raise SystemExit(f'unknown workload: {workload}')

elapsed = time.time() - started
out = {
    'worker': worker,
    'workers': workers,
    'workload': workload,
    'scale': scale,
    'units': units,
    'elapsed': elapsed,
    'rate': units / elapsed if elapsed else 0,
    'result': result,
}
os.makedirs('cluster_parts', exist_ok=True)
with open(f'cluster_parts/worker-{worker:02d}.json','w') as f:
    json.dump(out, f, indent=2)
print(json.dumps(out))
