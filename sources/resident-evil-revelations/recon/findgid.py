import struct,zlib,sys
d=open(sys.argv[1],'rb').read()
shoff,=struct.unpack('>I',d[0x20:0x24]); shentsize,shnum,shstrndx=struct.unpack('>HHH',d[0x2e:0x34])
S=[]
for i in range(shnum):
    o=shoff+i*shentsize
    nm,ty,fl,addr,off,sz,lk,inf,al,es=struct.unpack('>IIIIIIIIII',d[o:o+40])
    raw=b''
    if ty!=8 and sz:
        raw=d[off:off+sz]
        if fl&0x08000000:
            raw=zlib.decompress(raw[4:])
    S.append(dict(nm=nm,ty=ty,fl=fl,addr=addr,raw=raw))
sh=S[shstrndx]['raw']
for s in S:
    e=sh.index(b'\0',s['nm']); s['name']=sh[s['nm']:e].decode()
import pickle
text=[s for s in S if s['name']=='.text'][0]
print('text',hex(text['addr']),len(text['raw']))
for s in S:
    if s['name'].startswith('.fimport') or s['name'].startswith('.dimport'): print(s['name'],hex(s['addr']),len(s['raw']))
pickle.dump(S,open('secs.pkl','wb'))
