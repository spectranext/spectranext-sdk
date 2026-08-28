; process
; ssize_t write(int handle, void *buf, size_t len);
PUBLIC write
	include "spectranet.asm"
.write
	push	ix
	ld	ix, 4
	add	ix, sp

	ld	c, (ix+0)
	ld	b, (ix+1)
	ld	l, (ix+2)
	ld	h, (ix+3)
	ld	a, (ix+4)
	pop	ix

	; A=handle, HL=buf, BC=len
	IXCALL WRITE

	jr	c, write_error
	ld	h, b
	ld	l, c
	ret

write_error:
	ld	hl, -1
	ret
