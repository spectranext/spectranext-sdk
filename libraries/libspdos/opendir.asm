; process
; int opendir(char *name);
PUBLIC opendir
	include "spectranet.asm"
.opendir
	pop	bc
	pop	hl
	push	hl
	push	bc

	push	ix
	IXCALL OPENDIR
	pop	ix

	jr	c, opendir_error
	ld	h, 0
	ld	l, a
	ret

opendir_error:
	ld	hl, -1
	ret
