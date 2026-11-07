"""Independent Zone Rush challenger estimating rival intentions before selecting a route."""
from collections import deque


DEFAULT_CONFIG = {"upgrade": 1.65, "denial": .55, "cash": 1.10, "intercept": .95,
                  "defense": 1.05, "risk": 1.45}
BOUNDS = {"upgrade": (.8,3.0), "denial": (.12,1.3), "cash": (.5,2.2),
          "intercept": (0.,2.3), "defense": (.25,2.0), "risk": (.35,3.)}
CONFIG = dict(DEFAULT_CONFIG)
_history = {}
_DIRS = (("NORTH",-1,0),("EAST",0,1),("SOUTH",1,0),("WEST",0,-1))
_ADJ = tuple(tuple((a,8*(i//8+r)+i%8+c) for a,r,c in _DIRS
                   if 0<=i//8+r<8 and 0<=i%8+c<8) for i in range(64))
_DIST = tuple(tuple(abs(i//8-j//8)+abs(i%8-j%8) for j in range(64)) for i in range(64))


def _observe(state,cells,pos):
    me=state.bot_id
    owner=tuple(c.owner for c in cells)
    levels=tuple(c.is_upgraded for c in cells)
    frozen=[False]+[cells[pos[s]].is_frozen for s in range(1,5)]
    old=_history.get(me)
    start=(sum(bool(s) for s in owner)==4 and not any(levels)
           and all(cells[pos[s]].is_home and owner[pos[s]]==s for s in range(1,5)))
    ready="SHIELD" in state.legal_actions
    if old is None or (start and (old["turn"]>=80 or sum(bool(s) for s in old["owner"])>4 or any(old["levels"]))):
        memory={"turn":1, "scores":[0]*5, "progress":0, "cooldown":[0]*5, "persistence":[.65]*5}
    else:
        memory=old
        memory["turn"]=min(80,memory["turn"]+1)
        cool=[max(0,t-1) for t in old["cooldown"]]
        old_pos=old["positions"]
        for s in range(1,5):
            p=old_pos[s]
            defender=old["owner"][p]
            if defender and defender!=s and not old["frozen"][s]:
                stayed=pos[s]==p
                memory["persistence"][s]=.84*memory["persistence"][s]+.16*stayed
                if stayed and frozen[s] and not frozen[defender] and old_pos[defender]==pos[defender]:
                    cool[defender]=4
            if pos[s]==p and not old["frozen"][s] and frozen[s] and defender in (0,s):
                cool[s]=4
        if ready:
            cool[me]=0
        elif old["ready"] and not frozen[me]:
            cool[me]=4
        memory["cooldown"]=cool
        p=pos[me]
        continuing=(old_pos[me]==p and not frozen[me] and not old["frozen"][me]
                    and (ready or not old["ready"]) and owner[p]==old["owner"][p]
                    and levels[p]==old["levels"][p])
        memory["progress"]=min(2,old["progress"]+1) if continuing else 0
        for i,c in enumerate(cells):
            s=owner[i]
            if s:
                memory["scores"][s]+=c.base_points*(1+levels[i])
                if old["owner"][i] and old["owner"][i]!=s:
                    memory["scores"][s]+=8*c.base_points*(1+old["levels"][i])
    memory.update(owner=owner,levels=levels,positions=pos,frozen=frozen,ready=ready)
    _history[me]=memory
    return memory


def _intent(cells,s,pos,left):
    """Allocate rival's predicted first step among near-optimal expansion or raid targets."""
    p=pos[s]
    if cells[p].is_frozen:
        return {p:1.}
    routes=[(j,_DIST[j]) for _,j in _ADJ[p] if not cells[j].occupant]
    quality={}
    for i,c in enumerate(cells):
        if (i!=p and c.occupant) or (c.is_home and c.owner!=s):
            continue
        own=c.owner==s
        if own and c.is_upgraded:
            continue
        d=_DIST[p][i]
        t=d+(3 if own or c.is_upgraded else 1)
        if t>left:
            continue
        horizon=min(left-t+1,32)
        gain=c.base_points*(horizon*(1.45 if own else 1.0)
                           + ((8+.4*horizon)*(1+c.is_upgraded) if c.owner and not own else 0))
        rate=gain/t
        first=[p] if d==0 else [j for j,dist in routes if dist[i]<d]
        for j in first:
            quality[j]=max(quality.get(j,0.),rate)
    if not quality:
        return {p:1.}
    peak=max(quality.values())
    weights={j:(v/peak)**4 for j,v in quality.items()}
    total=sum(weights.values())
    return {j:v/total for j,v in weights.items()}


def act(state):
    cells=[c for row in state.board for c in row]
    me=state.bot_id
    pos=[0]*5
    for i,c in enumerate(cells):
        if c.occupant:
            pos[c.occupant]=i
    m=_observe(state,cells,pos)
    legal=state.legal_actions
    if len(legal)==1:
        return legal[0]
    cfg=CONFIG
    p=pos[me]
    left=81-m["turn"]
    rivals=[s for s in range(1,5) if s!=me]
    intent={s:_intent(cells,s,pos,left) for s in rivals}
    pressure=[min(_DIST[pos[s]][i] for s in rivals) for i in range(64)]
    our_score=m["scores"][me]
    threat={s:.4+.6/(1+abs(our_score-m["scores"][s])/(50+3*left)) for s in rivals}
    bias={}
    for a,j in _ADJ[p]:
        if a not in legal or cells[j].occupant:
            continue
        impact=0.
        for s in rivals:
            chance=intent[s].get(j,0.)
            if not chance:
                continue
            c=cells[j]
            priority=(1. if c.owner==me else 0. if c.owner==s else 1. if state.is_priority_token else .33)
            origin=cells[pos[s]]
            # A blocked rival can raid our tile by staying. Avoid handing it that option.
            consolation=(8 if origin.owner==me and not origin.is_upgraded else
                         3 if origin.owner not in (0,s) and not origin.is_home else 1)
            value=c.base_points*(2.0 if c.owner==me else 1.1)
            impact+=chance*(priority*cfg["intercept"]*threat[s]*(value-consolation)
                            -(1-priority)*1.7)
        bias[a]=impact
    # Tie equal-length routes by their estimated first-turn collision consequences.
    d=[99]*64
    d[p]=0
    first=[None]*64
    first[p]="STAY"
    q=deque()
    for a,j in sorted(_ADJ[p],key=lambda x:-bias.get(x[0],-999)):
        if a in bias:
            d[j]=1; first[j]=a; q.append(j)
    while q:
        i=q.popleft()
        for _,j in _ADJ[i]:
            if d[j]==99 and not cells[j].occupant:
                d[j]=d[i]+1; first[j]=first[i]; q.append(j)
    best,action=-1.,"STAY"
    for i,c in enumerate(cells):
        mine=c.owner==me
        if (mine and c.is_upgraded) or (c.is_home and not mine):
            continue
        work=3 if mine or c.is_upgraded else 1
        if i==p:
            work=max(1,work-m["progress"])
        cost=d[i]+work
        if cost>left:
            continue
        horizon=min(left-cost+1,80 if c.is_home else 15+5*pressure[i]+(6 if mine else 0))
        value=c.base_points*horizon*(cfg["upgrade"] if mine else 1.)
        delay=0.
        if c.owner and not mine:
            s=c.owner
            value+=c.base_points*(1+c.is_upgraded)*(8*cfg["cash"]+threat[s]*cfg["denial"]*horizon)
            if m["cooldown"][s]<cost and not cells[pos[s]].is_frozen:
                delay=cfg["risk"]*(1.15 if c.is_upgraded else .55)
        a=first[i]
        rate=value/(cost+delay) + bias.get(a,0)
        if rate>best:
            best,action=rate,a
    if "SHIELD" in legal:
        gain=0.
        miss=1.
        for s in rivals:
            c=cells[pos[s]]
            if c.owner!=me or c.is_frozen:
                continue
            stay=.55*intent[s].get(pos[s],0)+.45*m["persistence"][s]
            v=(0 if c.is_home else c.base_points*(1+c.is_upgraded)
               *(8*threat[s]+min(left,7 if c.is_upgraded else 4)))
            gain+=stay*(v+threat[s]*min(left-1,2)*3)
            miss*=1-stay
        if cfg["defense"]*gain > max(1.,best)*(.55+1.25*miss):
            action="SHIELD"
    return action if action in legal else "STAY"
