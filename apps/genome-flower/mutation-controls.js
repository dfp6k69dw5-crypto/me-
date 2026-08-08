// Genome Flower mutation control helpers.
// Converts user-facing sequencing sliders into mutation operator settings.
export const DEFAULT_MUTATION_PROFILE = Object.freeze({
  mutationRate: 0.20,
  clusterSize: 0.18,
  transitionBias: 0.55,
  indelBias: 0.08,
  hotspotBias: 0.35,
  regulatoryBias: 0.55,
  duplicationBias: 0.06,
  inversionBias: 0.05,
  recombinationBias: 0.10,
  developmentalNoise: 0.18
});

export function normalizeMutationProfile(p={}){
  const out={};
  for(const [k,v] of Object.entries(DEFAULT_MUTATION_PROFILE)){
    const n=Number(p[k]);
    out[k]=Number.isFinite(n)?Math.max(0,Math.min(1,n)):v;
  }
  return out;
}

export function mutationCount(profile, genomeLength, big=false){
  const p=normalizeMutationProfile(profile);
  const base=big?18:1;
  const rateScale=1+Math.pow(p.mutationRate,1.7)*(big?110:32);
  const clusterScale=1+p.clusterSize*(big?18:7);
  return Math.max(1,Math.min(genomeLength,Math.round(base*rateScale*clusterScale)));
}

export function weightedChoice(rng, entries){
  let total=0;
  for(const [,w] of entries) total+=Math.max(0,w);
  if(total<=0) return entries[0][0];
  let x=rng()*total;
  for(const [name,w0] of entries){
    x-=Math.max(0,w0);
    if(x<=0) return name;
  }
  return entries[entries.length-1][0];
}
