; process
; int rename(const char *s, const char *d);
PUBLIC rename
	include "spectranet.asm"
.rename
	pop	bc
	pop	de
	pop	hl
	push	hl
	push	de
	push	bc

	push	ix
	IXCALL RENAME
	pop	ix

	jr	c, rename_error
	ld	hl, 0
	ret

rename_error:
	ld	hl, -1
	ret
