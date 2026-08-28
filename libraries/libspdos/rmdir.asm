; process
; int rmdir(char *name);
PUBLIC rmdir
	include "spectranet.asm"
.rmdir
	pop	bc
	pop	hl
	push	hl
	push	bc

	push	ix
	IXCALL RMDIR
	pop	ix

	jr	c, rmdir_error
	ld	hl, 0
	ret

rmdir_error:
	ld	hl, -1
	ret
