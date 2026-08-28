; process
; int setmountpoint(int mount_point);
PUBLIC setmountpoint
	include "spectranet.asm"
.setmountpoint
	pop	bc
	pop	hl
	push	hl
	push	bc

	push	ix
	ld	a, l
	HLCALL SETMOUNTPOINT
	pop	ix

	jr	c, setmount_error
	ld	hl, 0
	ret

setmount_error:
	ld	hl, -1
	ret
