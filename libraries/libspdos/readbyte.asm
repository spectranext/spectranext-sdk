; process
; int readbyte(int fd);
PUBLIC readbyte
	include "spectranet.asm"
.readbyte
	pop	bc
	pop	hl
	push	hl
	push	bc

	push	ix
	ld	a, l
	dec	sp
	dec	sp
	ld	hl, 0
	add	hl, sp
	ex	de, hl
	ld	bc, 1
	HLCALL READ

	ld	hl, 0
	add	hl, sp
	ld	l, (hl)
	ld	h, 0
	ld	a, b
	or	c
	jr	z, readbyte_error

	inc	sp
	inc	sp
	pop	ix
	and	a
	ret

readbyte_error:
	inc	sp
	inc	sp
	pop	ix
	ld	hl, -1
	scf
	ret
