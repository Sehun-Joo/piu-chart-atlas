export function rankCharts(charts, {x=10, metric='average', level='all', mode='all', search='', direction='desc'}={}) {
  x = Math.max(1, Math.min(300, Math.trunc(Number(x)) || 1));
  return charts.filter(c=>c.level>=20 && ['S','D'].includes(c.mode))
    .filter(c=>(level==='all'||c.level===Number(level))&&(mode==='all'||c.mode===mode)&&c.title.toLowerCase().includes(search.trim().toLowerCase()))
    .map(c=>{const top=[...c.scores].sort((a,b)=>b-a).slice(0,x); return {...c, used:top.length, average:top.length?top.reduce((a,b)=>a+b,0)/top.length:null};})
    .filter(c=>metric!=='average'||c.used===x)
    .sort((a,b)=>{const av=a[metric],bv=b[metric];if(av===null)return bv===null?a.title.localeCompare(b.title):1;if(bv===null)return -1;return (direction==='asc'?1:-1)*(av-bv)||a.title.localeCompare(b.title)||a.level-b.level||a.mode.localeCompare(b.mode);});
}
