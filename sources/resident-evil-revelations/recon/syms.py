import pickle,struct,sys
S=pickle.load(open('secs.pkl','rb'))
sym=[s for s in S if s['ty']==2][0]['raw']; st=[s for s in S if s['ty']==3 and len(s['raw'])>1000][0]['raw']
pat=sys.argv[1]
for i in range(0,len(sym),16):
    nm,val,sz,info,oth,shn=struct.unpack('>IIIBBH',sym[i:i+16])
    e=st.index(b'\0',nm); n=st[nm:e].decode(errors='replace')
    if pat in n: print(hex(val),sz,n[:150])
