; Paged-out variant: unlike the VFS entry points, this is a direct sysvar
; read, so callers must explicitly page Spectranet in first.
PUBLIC getmountpoint
	include "spectranet.asm"
.getmountpoint
	push	ix
	call	PAGEIN
	ld	a, (0x3F6F)
	ld	l, a
	ld	h, 0
	pop	ix
	jp	PAGEOUT
