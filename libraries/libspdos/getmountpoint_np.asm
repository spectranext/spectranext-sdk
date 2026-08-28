; Non-paging variant for modules which already run with Spectranet paged in.
PUBLIC getmountpoint
.getmountpoint
	push	ix
	ld	hl, 0x3F6F
	ld	a, (hl)
	pop	ix
	ld	h, 0
	ld	l, a
	ret
