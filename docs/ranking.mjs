// A descriptive evidence index, not an estimated probability or bias correction.
// Fixed 100-entry depth avoids comparing different leaderboard denominators.
export function scoreability(scores, target=990000) {
  target = Math.max(900000, Math.min(1000000, Math.trunc(Number(target)) || 990000));
  const top = scores.filter(s=>Number.isFinite(s)&&s>=0&&s<=1000000).sort((a,b)=>b-a).slice(0,100);
  const ease = top.reduce((sum,s)=>sum+Math.max(0,Math.min(1,(s-(target-20000))/20000)),0);
  return {ease, targetCount: scores.filter(s=>s>=target).length, evidenceCount:top.length};
}

export function rankCharts(charts, {x=10, metric='ease', level='all', mode='all', search='', direction='desc', target=990000}={}) {
  x = Math.max(1, Math.min(300, Math.trunc(Number(x)) || 1));
  return charts.filter(c=>c.level>=20 && ['S','D'].includes(c.mode))
    .filter(c=>(level==='all'||c.level===Number(level))&&(mode==='all'||c.mode===mode)&&c.title.toLowerCase().includes(search.trim().toLowerCase()))
    .map(c=>{const top=[...c.scores].sort((a,b)=>b-a).slice(0,x); return {...c, ...scoreability(c.scores,target), used:top.length, average:top.length?top.reduce((a,b)=>a+b,0)/top.length:null};})
    .filter(c=>metric!=='average'||c.used===x)
    .sort((a,b)=>{const av=a[metric],bv=b[metric];if(av===null)return bv===null?a.title.localeCompare(b.title):1;if(bv===null)return -1;return (direction==='asc'?1:-1)*(av-bv)||a.title.localeCompare(b.title)||a.level-b.level||a.mode.localeCompare(b.mode);});
}
