; process
; int umount(int mount_point);
PUBLIC umount
	include "spectranet.asm"
.umount
	pop	bc
	pop	hl
	push	hl
	push	bc

	push	ix
	ld	a, l
	HLCALL UMOUNT
	pop	ix

	jr	c, umount_error
	ld	hl, 0
	ret

umount_error:
	ld	hl, -1
	ret
