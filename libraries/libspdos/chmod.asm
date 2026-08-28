; process
; int chmod(const char *path, mode_t mode);
PUBLIC chmod
	include "spectranet.asm"
.chmod
	pop	bc
	pop	de
	pop	hl
	push	hl
	push	de
	push	bc

	push	ix
	IXCALL CHMOD
	pop	ix

	jr	c, chmod_error
	ld	hl, 0
	ret

chmod_error:
	ld	hl, -1
	ret
