import {FlowerGenome} from '../apps/genome-flower/flower-genome.js';
import {classifyFlower} from '../apps/genome-flower/photoreal-flower-renderer.js';

// Distribution sanity check: body-plan labels must correspond to reachable phenotypes.
const counts={};
for(let seed=1;seed<=512;seed++){
  const g=new FlowerGenome({seed:(Math.imul(seed,2654435761)>>>0)});
  const type=classifyFlower(g);
  counts[type]=(counts[type]||0)+1;
}
console.log('Genome Flower architecture distribution:',counts);
const types=Object.keys(counts);
if(types.length<6)throw new Error(`Architecture collapse: only ${types.length} types reached`);
const max=Math.max(...Object.values(counts));
if(max>360)throw new Error(`Architecture collapse: one type dominates ${max}/512 genomes`);
