import re,glob
names={'a1':'bare copilot','a2':'stock nav-pilot','a3':'nais/pilot'}
# the four planted defects, each something a linter does not fail the build on
DEFECTS=[
 ('blank-assigned error', r'_ =\s*s\.db\.Close|blank|_\s*=|discard(ed|s)? the error|ignor\w+ .{0,20}error|errcheck'),
 ('db.Close in a handler', r'Close\(\)'),
 ('unsanitised user input logged', r'sanitiz|sanitis|log injection|inject\w* .{0,20}log|newline.{0,20}log|reason.{0,30}log'),
 ('interface with no implementation updated', r'\bStore\b.{0,80}(unused|no implement|not implemented|dead|never)|implementations? of .{0,10}Store'),
 ('skip with no CI switch', r'REQUIRE|t\.Skip.{0,120}(silent|never|always|CI)|skip\w*.{0,60}(silently|green|unnoticed)'),
]
for a in ('a1','a2','a3'):
    rows=[]
    for f in sorted(glob.glob(f'gr-{a}-*.txt')):
        t=re.sub(r'\x1b\[[0-9;]*m','',open(f,encoding='utf-8',errors='replace').read())
        body=re.split(r'\nChanges\s+\+',t)[0]
        hits=[lbl for lbl,rx in DEFECTS if re.search(rx,body,re.I|re.S)]
        mt=re.search(r'Tokens\s+↑\s*([\d.]+)([km]?)',t); up=0
        if mt: up=float(mt.group(1))*(1000 if mt.group(2)=='k' else 1_000_000 if mt.group(2)=='m' else 1)
        mc=re.search(r'AI Credits\s+([\d.]+)',t); cr=float(mc.group(1)) if mc else 0
        rows.append((len(hits),hits,int(up),cr))
    if not rows: continue
    print('%-17s n=%d  defects=%.1f/%d  avg↑tok=%-9s avg_cred=%.2f' % (names[a],len(rows),
        sum(r[0] for r in rows)/len(rows),len(DEFECTS),
        format(sum(r[2] for r in rows)//len(rows),','),sum(r[3] for r in rows)/len(rows)))
    missed=[lbl for lbl,_ in DEFECTS if not any(lbl in r[1] for r in rows)]
    if missed: print('     never found:',', '.join(missed))
