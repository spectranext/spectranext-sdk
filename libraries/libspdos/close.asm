; process
; int close(int handle);
PUBLIC close
	include "spectranet.asm"
.close
	pop	bc
	pop	hl
	push	hl
	push	bc

	push	ix
	ld	a, l
	HLCALL VCLOSE
	pop	ix

	jr	c, close_error
	ld	hl, 0
	ret

close_error:
	ld	hl, -1
	ret
