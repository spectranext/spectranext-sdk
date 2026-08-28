; process
; int mkdir(char *name);
PUBLIC mkdir
	include "spectranet.asm"
.mkdir
	pop	bc
	pop	hl
	push	hl
	push	bc

	push	ix
	IXCALL MKDIR
	pop	ix

	jr	c, mkdir_error
	ld	hl, 0
	ret

mkdir_error:
	ld	hl, -1
	ret
