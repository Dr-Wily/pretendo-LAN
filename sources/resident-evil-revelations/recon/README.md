Scripts used to recover the constants in ../RECON.md from the retail
executable (`BioRevHD.rpx`, not included). Run with `python -I`:

    python -I unrpx.py BioRevHD.rpx bio.bin    # zlib sections -> flat dump
    python -I findgid.py BioRevHD.rpx          # section table -> secs.pkl
    python -I refs.py "string"                 # ASCII string -> code xrefs
    python -I dis.py 0x2a902e0 0x2a90360       # capstone PPC disassembly

The access key was found by scanning `.rodata` for UTF-16BE 8-hex literals and
keeping the one referenced from code (see RECON.md). `dis.py` needs
`capstone`. Outputs (`*.bin`, `secs.pkl`) are git-ignored.