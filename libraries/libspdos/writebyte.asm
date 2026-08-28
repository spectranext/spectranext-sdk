; process
; int writebyte(int handle, int c);
PUBLIC writebyte
	include "spectranet.asm"
.writebyte
	pop	bc
	pop	hl
	pop	de
	push	de
	push	hl
	push	bc

	push	ix
	ld	a, e
	; Stack: ix(2), ret(2), c(2), handle(2) — `c` starts at sp+4
	ld	hl, 4
	add	hl, sp
	ld	bc, 1
	IXCALL WRITE

	pop	ix
	jr	c, writebyte_error
	ld	h, b
	ld	l, c
	ret

writebyte_error:
	ld	hl, -1
	ret
