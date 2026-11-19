"""Experimental ridge player/chart effects; conditional on observed clears."""
import math
from collections import defaultdict

def fit_effects(records, penalty=20, iterations=500):
    """Minimize squared log-deficit residuals + penalty * sum(chart_effect**2)."""
    players, charts = defaultdict(list), defaultdict(list)
    for p,c,s in records:
        y=math.log1p(1000000-s)
        players[p].append((c,y)); charts[c].append((p,y))
    if not records: return {}, False
    mu=sum(math.log1p(1000000-s) for _,_,s in records)/len(records)
    a=dict.fromkeys(players,0.0); b=dict.fromkeys(charts,0.0)
    for _ in range(iterations):
        old=list(a.values())+list(b.values())+[mu]
        for p,rows in players.items(): a[p]=sum(y-mu-b[c] for c,y in rows)/len(rows)
        for c,rows in charts.items(): b[c]=sum(y-mu-a[p] for p,y in rows)/(len(rows)+penalty)
        mu=sum(y-a[p]-b[c] for p,rows in players.items() for c,y in rows)/len(records)
        if max(abs(x-y) for x,y in zip(old,list(a.values())+list(b.values())+[mu]))<1e-7:
            return b,True
    return b,False

def annotate(charts):
    groups=defaultdict(list)
    for c in charts:
        c['adjusted']=None
        groups[c['mode'],c['level']].append(c)
    fitted=0
    for group in groups.values():
        by_player=defaultdict(set)
        for c in group:
            for p,s in c.get('_observations',[]): by_player[p].add(c['id'])
        # Only shared players identify differences. Keep one connected component;
        # disconnected populations cannot support a common ranking.
        neighbors=defaultdict(set)
        for ids in by_player.values():
            for c in ids: neighbors[c].update(ids)
        remaining=set(neighbors); components=[]
        while remaining:
            todo=[remaining.pop()]; comp=set(todo)
            while todo:
                for nxt in neighbors[todo.pop()] & remaining:
                    remaining.remove(nxt);comp.add(nxt);todo.append(nxt)
            components.append(comp)
        if not components: continue
        largest=max(components,key=lambda comp:(len(comp),sorted(comp)))
        if len(largest)<3: continue
        rows=[]; counts=defaultdict(int)
        for c in group:
            if c['id'] not in largest: continue
            for p,s in c.get('_observations',[]):
                if len(by_player[p])>=2:
                    rows.append((p,c['id'],s));counts[c['id']]+=1
        if len({p for p,_,_ in rows})<30: continue
        fits=[fit_effects(rows,k) for k in (5,20,50)]
        if not all(ok for _,ok in fits): continue
        for c in group:
            key=c['id']
            if counts[key]<10: continue
            values=[-effects[key] for effects,_ in fits]
            c['adjusted']=values[1]
            c['modelSupport']=counts[key]
            c['modelSensitivity']=[min(values),max(values)]
            fitted+=1
    # No player keys or per-player records are published.
    for c in charts: c.pop('_observations',None)
    return {'method':'player-fixed-chart-ridge-v1','fittedCharts':fitted,'penalty':20,'sensitivityPenalties':[5,20,50],
            'scope':'within mode and level; observed clears only','validatedOnRealData':False}
