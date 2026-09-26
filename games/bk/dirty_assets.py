"""DIRTY ROOM dev: v1.1 asset table renumbered to v1.0 IDs (retail bytes; dev ROM only, never published)."""
import json,sys
sys.path.insert(0,'D:/n64work/bk-cleanroom')
from games.bk import assetfs as a, renumber as r
es=a.parse(open('D:/n64work/bk/dirty/assets.v11.bin','rb').read())
m={i:i for i in range(0x1000)}; m.update({int(k,16):int(v,16) for k,v in json.load(open('D:/n64work/bk-cleanroom/games/bk/spec/asset_renumber.json'))['v11_to_v10'].items()})
out=r.apply(es,m)
for dst in (0x6e9,0x6ea):
    s=out[0x6eb]; out[dst]=a.Entry(dst,s.seg,s.compressed,s.flags,s.data,s.raw)
b=a.build(out,keep_raw=True); open('D:/n64work/bk/dirty/assets.v10num.bin','wb').write(b); print(len(out),hex(len(b)))
