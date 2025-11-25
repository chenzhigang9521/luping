import re
p='resources/fonts/NotoSans-Regular.ttf'
with open(p,'rb') as f:
    b=f.read()
# extract ASCII sequences 3+ chars
seqs=re.findall(b'[\x20-\x7E]{3,}', b)
res=[s.decode('ascii',errors='ignore') for s in seqs]
found=[s for s in res if 'Noto' in s or 'NOTO' in s or 'Sans' in s or 'sans' in s]
for s in found[:200]:
    print(s)
# search for UTF-16BE occurrences
u16 = b'N\x00o\x00t\x00o' 
u16_sans = b'N\x00o\x00t\x00o\x00 \x00S\x00a\x00n\x00s'
if u16 in b:
    print('found UTF-16BE Noto')
if u16_sans in b:
    print('found UTF-16BE Noto Sans')
print('---len sequences:', len(seqs))
print('---done')
