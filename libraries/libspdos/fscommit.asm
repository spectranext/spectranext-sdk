; process
; int fscommit(const char *path);
PUBLIC fscommit
	include "spectranet.asm"
.fscommit
	pop	bc
	pop	hl
	push	hl
	push	bc

	ld	de, 0x8000

	push	ix
	IXCALL CHMOD
	pop	ix

	jr	c, fscommit_error
	ld	hl, 0
	ret

fscommit_error:
	ld	hl, -1
	ret
