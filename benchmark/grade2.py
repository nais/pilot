import re,glob,json
import yaml, jsonschema
schema=json.load(open('feature.schema.json'))
names={'a1':'bare copilot','a2':'stock nav-pilot','a3':'nais/pilot'}
def extract(t):
    t=re.sub(r'\x1b\[[0-9;]*m','',t)
    body=re.split(r'\nChanges\s+\+',t)[0]
    m=list(re.finditer(r'```(?:ya?ml)?\n(.*?)```',body,re.S))
    if m: return m[-1].group(1)
    # last line that starts a top-level key, walk back to its block start
    idx=max(body.rfind('\nenvironmentKinds:'),body.rfind('\ndependencies:'),body.rfind('\nvalues:'),body.rfind('\ntimeout:'))
    if idx<0: return body
    seg=body[:idx+1]
    starts=[seg.rfind('\n'+k+':') for k in ('environmentKinds','dependencies','values','timeout')]
    s=min([x for x in starts if x>=0] or [idx])
    return body[s:]
for a in ('a1','a2','a3'):
    rows=[]
    for f in sorted(glob.glob(f'auth-{a}-*.txt')):
        t=open(f,encoding='utf-8',errors='replace').read()
        mt=re.search(r'Tokens\s+↑\s*([\d.]+)([km]?)',t); up=0
        if mt: up=float(mt.group(1))*(1000 if mt.group(2)=='k' else 1_000_000 if mt.group(2)=='m' else 1)
        mc=re.search(r'AI Credits\s+([\d.]+)',t); cr=float(mc.group(1)) if mc else 0
        ok=False; reqs=0; err=''
        try:
            d=yaml.safe_load(extract(t))
            if isinstance(d,dict):
                try: jsonschema.validate(d,schema); ok=True
                except jsonschema.ValidationError as e: err=e.message[:60]
                v=d.get('values') or {}
                reqs=sum([d.get('environmentKinds')==['management'], d.get('timeout') in ('90m','1h30m'),
                    bool(v.get('audit.endpoint',{}).get('required')), v.get('audit.token',{}).get('config',{}).get('secret') is True,
                    'computed' in (v.get('image.tag') or {}), 'mimir' in json.dumps(d.get('dependencies'))])
            else: err='not a mapping'
        except Exception as e: err=str(e)[:60]
        rows.append((int(up),cr,ok,reqs,err))
    print('%-17s n=%d schema=%d/%d reqs=%.1f/6 avg↑tok=%-9s avg_cred=%.2f' % (names[a],len(rows),
        sum(1 for r in rows if r[2]),len(rows),sum(r[3] for r in rows)/len(rows),
        format(sum(r[0] for r in rows)//len(rows),','),sum(r[1] for r in rows)/len(rows)))
    for r in rows:
        if r[4]: print('     err:',r[4])
