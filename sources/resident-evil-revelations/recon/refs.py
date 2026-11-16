import pickle,struct,sys
S=pickle.load(open('secs.pkl','rb'))
t=[s for s in S if s['name']=='.text'][0]
raw=t['raw'];base=t['addr'];n=len(raw)//4
w=struct.unpack('>%dI'%n,raw[:n*4])
def find_str(s):
    out=[]
    for sec in S:
        if sec['fl']&2 and sec['raw']:
            i=sec['raw'].find(s)
            while i>=0:
                out.append(sec['addr']+i); i=sec['raw'].find(s,i+1)
    return out
def xrefs(addr):
    hi=(addr+0x8000)>>16; lo=addr&0xffff
    r=[]
    for i,x in enumerate(w):
        if x>>26==15 and (x&0xffff)==hi and ((x>>16)&0x1f)==0:
            rd=(x>>21)&0x1f
            for j in range(i+1,min(i+8,n)):
                y=w[j]
                if y>>26 in (14,24) and (y&0xffff)==lo and ((y>>16)&0x1f)==rd: r.append(base+i*4);break
    return r
for s in sys.argv[1:]:
    for a in find_str(s.encode()):
        print(s,hex(a),[hex(x) for x in xrefs(a)])
