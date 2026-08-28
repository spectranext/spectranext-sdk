# libspectranet-style build: *_p.asm (HLCALL/IXCALL) + *_np.asm (direct CALL).
# libspdos.lib    — callable with Spectranet paged out (dispatcher stubs).
# libspdos_np.lib — direct jump table calls (Spectranet must be paged in).

# Like libspectranet: sources use one-line ``HLCALL sym`` / ``IXCALL sym``; ``genspdos.py``
# emits *_p.asm (dispatch) and *_np.asm (direct ``call sym``). Perl ``../scripts/makesources.pl``
# is equivalent if you prefer: ``$(MAKE) spdos_gen_pl``.
SPDOSGEN = python3 ./genspdos.py
SRCGEN = ../scripts/makesources.pl
PLIBNAME = libspdos
NPLIBNAME = libspdos_np
PASMFILES = libspdos.lst
NPASMFILES = libspdos_np.lst

PROCESS_ASM = mount.asm setmountpoint.asm open.asm close.asm read.asm write.asm \
	readbyte.asm writebyte.asm lseek.asm mkdir.asm rmdir.asm chdir.asm \
	getcwd.asm rename.asm unlink.asm remove.asm opendir.asm readdir.asm \
	closedir.asm umount.asm stat.asm stat_isdir.asm chmod.asm fscommit.asm

GEN_PASM = $(patsubst %.asm,%_p.asm,$(PROCESS_ASM))
GEN_NPASM = $(patsubst %.asm,%_np.asm,$(PROCESS_ASM))

all:	$(PROCESS_ASM) spdos_gen $(GEN_PASM) $(GEN_NPASM) $(PLIBNAME).lib $(NPLIBNAME).lib

spdos_gen:	$(PROCESS_ASM)
	$(SPDOSGEN)

spdos_gen_pl:	$(PROCESS_ASM)
	$(SRCGEN)

.PHONY:	spdos_gen spdos_gen_pl

$(PLIBNAME).lib: $(PASMFILES) $(GEN_PASM) getmountpoint_p.asm
	$(LIBLINKER) $(LIBLDFLAGS) -x$(PLIBNAME) @$(PASMFILES)

$(NPLIBNAME).lib: $(NPASMFILES) $(GEN_NPASM) getmountpoint_np.asm
	$(LIBLINKER) $(LIBLDFLAGS) -x$(NPLIBNAME) @$(NPASMFILES)

install: $(PLIBNAME).lib $(NPLIBNAME).lib
	$(CP) *.lib $(ZCCCFG)/../clibs
	$(CP) -r ./include $(ZCCCFG)/../../

include ../make.inc
