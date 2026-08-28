; process
; long lseek(int fd, long posn, int whence);
PUBLIC lseek
	include "spectranet.asm"
.lseek
	push	ix
	ld	ix, 4
	add	ix, sp

	ld	a, (ix+6)
	ld	l, (ix+2)
	ld	h, (ix+3)
	ld	e, (ix+4)
	ld	d, (ix+5)
	ld	c, (ix+0)
	pop	ix

	; A=fd, C=whence, DEHL=position
	IXCALL LSEEK

	jr	c, lseek_error
	ret

lseek_error:
	ld	hl, -1
	ld	de, 0xFFFF
	ret
