; process
; char *getcwd(char *buf, size_t buflen);
PUBLIC getcwd
	include "spectranet.asm"
.getcwd
	pop	bc
	pop	de
	pop	hl
	push	hl
	push	de
	push	bc

	push	hl
	push	ix
	ex	de, hl
	; DE = buf
	HLCALL GETCWD
	pop	ix
	pop	hl

	jr	c, getcwd_error
	ret

getcwd_error:
	ld	hl, 0
	ret
