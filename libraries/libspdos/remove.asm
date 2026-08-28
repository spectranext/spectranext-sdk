; process
; int remove(char *name);
PUBLIC remove
	include "spectranet.asm"
.remove
	pop	bc
	pop	hl
	push	hl
	push	bc

	push	ix
	IXCALL UNLINK
	pop	ix

	jr	c, remove_error
	ld	hl, 0
	ret

remove_error:
	ld	hl, -1
	ret
