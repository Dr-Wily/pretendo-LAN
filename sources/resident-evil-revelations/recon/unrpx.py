import struct,zlib,sys
d=open(sys.argv[1],'rb').read()
shoff,=struct.unpack('>I',d[0x20:0x24]); shentsize,shnum,shstrndx=struct.unpack('>HHH',d[0x2e:0x34])
secs=[]
for i in range(shnum):
    o=shoff+i*shentsize
    nm,ty,fl,addr,off,sz,lk,inf,al,es=struct.unpack('>IIIIIIIIII',d[o:o+40])
    secs.append([nm,ty,fl,addr,off,sz])
out=bytearray()
res=[]
for i,(nm,ty,fl,addr,off,sz) in enumerate(secs):
    if ty==8 or sz==0: continue
    raw=d[off:off+sz]
    if fl&0x08000000:
        n,=struct.unpack('>I',raw[:4]); raw=zlib.decompress(raw[4:])
    res.append((i,ty,addr,raw))
with open(sys.argv[2],'wb') as f:
    for i,ty,addr,raw in res:
        f.write(raw)
        print(i,ty,hex(addr),len(raw))
