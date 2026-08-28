; process
; int unlink(char *name);
PUBLIC unlink
	include "spectranet.asm"
.unlink
	pop	bc
	pop	hl
	push	hl
	push	bc

	push	ix
	IXCALL UNLINK
	pop	ix

	jr	c, unlink_error
	ld	hl, 0
	ret

unlink_error:
	ld	hl, -1
	ret
