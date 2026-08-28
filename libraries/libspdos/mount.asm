; process
; int mount(int mount_point, char* password, char* user_id, char* path, char* hostname, char *protocol);
PUBLIC mount
	include "spectranet.asm"
.mount
	push	ix
	ld	ix, 4
	add	ix, sp

	ld	a, (ix+10)

	; IX = parameter block layout; A = mount_point. Entry address in HL (HLCALL).
	HLCALL MOUNT

	jr	c, mount_error
	jr	z, mount_error

	pop	ix
	ld	hl, 0
	ret

mount_error:
	pop	ix
	ld	hl, -1
	ret
