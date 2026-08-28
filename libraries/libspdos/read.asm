; process
; ssize_t read(int handle, void *buf, size_t len);
PUBLIC read
	include "spectranet.asm"
	include "../../include/errno.inc"
.read
	push	ix
	ld	ix, 4
	add	ix, sp

	ld	c, (ix+0)
	ld	b, (ix+1)
	ld	l, (ix+2)
	ld	h, (ix+3)
	ex	de, hl
	ld	a, (ix+4)

	; A=handle, DE=buf, BC=len — HL free for HLCALL
	HLCALL READ

	jr	nc, read_success
	cp	EOF
	jr	z, read_eof
	ld	a, b
	or	c
	jr	z, read_error
read_success:
	pop	ix
	ld	h, b
	ld	l, c
	ret

read_eof:
	pop	ix
	ld	hl, 0
	ret

read_error:
	pop	ix
	ld	hl, -1
	ret
