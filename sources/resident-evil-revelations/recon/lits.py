import pickle,struct,sys
S=pickle.load(open('secs.pkl','rb'))
t=[s for s in S if s['name']=='.text'][0]
raw=t['raw'];base=t['addr'];n=len(raw)//4
w=struct.unpack('>%dI'%n,raw[:n*4])
lo_a,hi_a=int(sys.argv[1],16),int(sys.argv[2],16)
for i in range((lo_a-base)//4,(hi_a-base)//4):
    x=w[i]
    if x>>26==15 and ((x>>16)&0x1f)==0:
        rd=(x>>21)&0x1f;hi=x&0xffff
        for j in range(i+1,min(i+6,n)):
            y=w[j]
            if y>>26 in(14,24) and ((y>>16)&0x1f)==rd:
                lo=y&0xffff
                if y>>26==14 and lo&0x8000: lo-=0x10000
                v=((hi<<16)+lo)&0xffffffff if y>>26==14 else (hi<<16)|lo
                print(hex(base+i*4),'r%d'%rd,hex(v));break
