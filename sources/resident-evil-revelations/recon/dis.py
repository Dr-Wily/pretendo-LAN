import pickle,struct,sys
from capstone import *
S=pickle.load(open('secs.pkl','rb'))
t=[s for s in S if s['name']=='.text'][0]
raw=t['raw'];base=t['addr']
a,b=int(sys.argv[1],16),int(sys.argv[2],16)
md=Cs(CS_ARCH_PPC,CS_MODE_32|CS_MODE_BIG_ENDIAN)
for i in md.disasm(raw[a-base:b-base],a):
    print('%x: %s %s'%(i.address,i.mnemonic,i.op_str))
