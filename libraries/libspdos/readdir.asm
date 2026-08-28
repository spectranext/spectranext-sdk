; process
; int readdir(int dirhandle, void *buf);
PUBLIC readdir
	include "spectranet.asm"
.readdir
	pop	bc
	pop	de
	pop	hl
	push	hl
	push	de
	push	bc

	push	ix
	ld	a, l
	; A = dirhandle, DE = buf
	HLCALL READDIR
	pop	ix

	jr	c, readdir_error
	ld	hl, 0
	ret

readdir_error:
	ld	hl, -1
	ret
