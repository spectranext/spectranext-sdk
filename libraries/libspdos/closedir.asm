; process
; int closedir(int dirhandle);
PUBLIC closedir
	include "spectranet.asm"
.closedir
	pop	bc
	pop	hl
	push	hl
	push	bc

	push	ix
	ld	a, l
	HLCALL CLOSEDIR
	pop	ix

	jr	c, closedir_error
	ld	hl, 0
	ret

closedir_error:
	ld	hl, -1
	ret
