; process
; int isdir(const char* path);
PUBLIC isdir
	include "spectranet.asm"
.isdir
	; sccz80 RTL: stack under ret contains path.
	pop	bc
	pop	hl	; path
	push	hl
	push	bc

	push	ix
	ld	de, isdir_statbuf
	; ROM STAT: HL=path, DE=stat buffer
	IXCALL STAT

	pop	ix
	jr	c, isdir_no

	ld	hl, isdir_statbuf + 1
	ld	a, (hl)
	and	0x40	; S_IFDIR = 0x4000
	jr	z, isdir_no

	ld	hl, 1
	ret

isdir_no:
	ld	hl, 0
	ret

isdir_statbuf:
	defs	256
