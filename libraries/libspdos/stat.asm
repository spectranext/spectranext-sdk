; process
; int stat(const char* path, struct stat* buf);
PUBLIC stat
	include "spectranet.asm"
.stat
	push	ix
	ld	ix, 4
	add	ix, sp

	ld	e, (ix+0)
	ld	d, (ix+1)
	ld	l, (ix+2)
	ld	h, (ix+3)
	pop	ix

	; ROM STAT: HL=path, DE=stat buffer
	IXCALL STAT
	jr	c, stat_error
	ld	hl, 0
	ret

stat_error:
	ld	hl, -1
	ret
