; process
; int chdir(char *name);
PUBLIC chdir
	include "spectranet.asm"
.chdir
	pop	bc
	pop	hl
	push	hl
	push	bc

	push	ix
	IXCALL CHDIR
	pop	ix

	jr	c, chdir_error
	ld	hl, 0
	ret

chdir_error:
	ld	hl, -1
	ret
