import re,glob,sys
names={'a1':'bare copilot','a2':'stock nav-pilot','a3':'nais/pilot'}
# each rubric item: label, regex that must appear in the answer
RUBRIC=[
 ('canary ci-nais',            r'\bci-nais\b'),
 ('merge is the deploy',       r'(merge\w*\s+(to\s+)?main|merging)\b.{0,80}\b(deploy|ship|releas)|no separate release'),
 ('fasit is the delivery path',r'\bfasit\b'),
 ('environmentKinds split',    r'environmentKind|\bmanagement\b.{0,60}\btenant\b|\btenant\b.{0,60}\bmanagement\b'),
 ('onprem called out',         r'\bon-?prem\b'),
 ('verify in dev first',       r'\bdev-nais\b|\bdev\b.{0,40}\bfirst\b'),
 ('platform org header',       r'X-Scope-OrgID.{0,40}nais|orgid.{0,20}nais'),
 ('right observability host',  r'(mimir|loki|grafana)\.[a-z-]*\.?cloud\.nais\.io|mimir\.<tenant>'),
 ('fan-out to all tenants',    r'\ball tenants\b|every tenant|fan[- ]?out'),
 ('back-out path',             r'\brevert\b|\broll ?back\b|redeploy the previous'),
]
for a in ('a1','a2','a3'):
    rows=[]
    for f in sorted(glob.glob(f'rollout-{a}-*.txt')):
        t=re.sub(r'\x1b\[[0-9;]*m','',open(f,encoding='utf-8',errors='replace').read())
        body=re.split(r'\nChanges\s+\+',t)[0].lower()
        hits=[lbl for lbl,rx in RUBRIC if re.search(rx,body,re.I)]
        mt=re.search(r'Tokens\s+↑\s*([\d.]+)([km]?)',t); up=0
        if mt: up=float(mt.group(1))*(1000 if mt.group(2)=='k' else 1_000_000 if mt.group(2)=='m' else 1)
        mc=re.search(r'AI Credits\s+([\d.]+)',t); cr=float(mc.group(1)) if mc else 0
        rows.append((len(hits),hits,int(up),cr))
    if not rows: continue
    print('%-17s n=%d  rubric=%.1f/%d  avg↑tok=%-9s avg_cred=%.2f' % (names[a],len(rows),
        sum(r[0] for r in rows)/len(rows),len(RUBRIC),format(sum(r[2] for r in rows)//len(rows),','),
        sum(r[3] for r in rows)/len(rows)))
    missed=[lbl for lbl,_ in RUBRIC if not any(lbl in r[1] for r in rows)]
    if missed: print('     never mentioned:', ', '.join(missed))
