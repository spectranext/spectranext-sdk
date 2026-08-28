; process
; int open(char *name, int flags, mode_t mode);
PUBLIC open
	include "spectranet.asm"
.open
	push	ix
	ld	ix, 4
	add	ix, sp

	ld	c, (ix+0)
	ld	b, (ix+1)
	ld	e, (ix+2)
	ld	d, (ix+3)
	ld	l, (ix+4)
	ld	h, (ix+5)
	pop	ix

	; HL=filename, DE=flags, BC=mode
	IXCALL OPEN

	jr	c, open_error
	ld	h, 0
	ld	l, a
	jr	open_end

open_error:
	ld	hl, -1

open_end:
	ret
