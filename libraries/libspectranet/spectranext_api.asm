; process
; Stubs for F_spectranext_op (spectranet-firmware/rom/spectranext.asm).
; push/pop ix to preserve the caller's frame pointer.
	include "spectranet.asm"

CMD_GET_STATUS		equ 0
CMD_WIFI_SCAN		equ 1
CMD_WIFI_GET_AP	    equ 2
CMD_WIFI_CONNECT	equ 3
CMD_WIFI_DISCONNECT	equ 4
CMD_DNS			    equ 5
CMD_ENGINECALL		equ 6
CMD_GET_MESSAGE		equ 7
CMD_XFS_READ		equ 8

PUBLIC spectranext_get_controller_status
PUBLIC spectranext_wifi_scan_access_points
PUBLIC spectranext_wifi_get_access_point
PUBLIC spectranext_wifi_connect_access_point
PUBLIC spectranext_wifi_disconnect
PUBLIC spectranext_gethostbyname
PUBLIC spectranext_enginecall
PUBLIC spectranext_xfs_read

se_fail:
	pop		ix
	ld		hl, -1
	ret

; int8_t spectranext_get_controller_status(int8_t *wifi_connection_out, uint32_t *ipv4_out);
; sccz80: args pushed LTR; top of stack after ret = right param (ipv4_out), then left (wifi_connection_out).
; ROM: DE = ipv4_out; HL = wifi_connection_out; returns B = controller_status, C = wifi_connection.
spectranext_get_controller_status:
	pop		bc
	pop		de		; ipv4_out (2nd param)
	pop		hl		; wifi_connection_out (1st param)
	push	bc

	push	ix
	ld		a, CMD_GET_STATUS
	IXCALL	SPECTRANEXT
	pop		ix

	jr		c, spectranext_get_controller_status_fail

	ld		a, c
	ld		(hl), a	; store wifi_connection

	ld		a, b
	ld		h, 0	; return controller_status
	ld		l, a
	ret

spectranext_get_controller_status_fail:
	ld		hl, -1
	ret

; int8_t spectranext_wifi_scan_access_points(void); success: H=0, L=count. Error: H=0, L=255 (-1), not ld hl,-1.
spectranext_wifi_scan_access_points:
	push	ix
	ld		a, CMD_WIFI_SCAN
	IXCALL	SPECTRANEXT
	pop		ix
	jr		c, spectranext_wifi_scan_access_points_fail
	ld		h, 0
	ld		l, a
	ret
spectranext_wifi_scan_access_points_fail:
	ld		h, 0
	ld		l, 255		; -1
	ret

; int8_t spectranext_wifi_get_access_point(uint8_t ap, char *result_name); success: 0, error: -1.
; sccz80: char pushed as word; top after ret = result_name, then ap word (C = index).
; ROM: C = index, DE = result_name (ROM fills from device staging).
spectranext_wifi_get_access_point:
	pop		hl
	pop		de		; result_name (2nd param)
	pop		bc		; ap (1st param; C = index)
	push	hl

	push	ix
	ld		a, CMD_WIFI_GET_AP
	IXCALL	SPECTRANEXT
	pop		ix
	jr		c, spectranext_wifi_get_access_point_fail
	ld		hl, 0
	ret
spectranext_wifi_get_access_point_fail:
	ld		hl, -1
	ret

; int8_t spectranext_wifi_connect_access_point(const char* ssid, const char* password); success: 0, error: -1.
; sccz80 LTR: top after ret = password, then ssid. ROM: HL = ssid, DE = password.
spectranext_wifi_connect_access_point:
	pop		bc
	pop		de		; password (2nd param)
	pop		hl		; ssid (1st param)
	push	bc

	push	ix
	ld		a, CMD_WIFI_CONNECT
	IXCALL	SPECTRANEXT
	pop		ix
	jr		c, spectranext_wifi_connect_access_point_fail
	ld		hl, 0
	ret
spectranext_wifi_connect_access_point_fail:
	ld		hl, -1
	ret

; int8_t spectranext_wifi_disconnect(void); success: 0, error: -1.
spectranext_wifi_disconnect:
	push	ix
	ld		a, CMD_WIFI_DISCONNECT
	IXCALL	SPECTRANEXT
	pop		ix
	jr		c, spectranext_wifi_disconnect_fail
	ld		hl, 0
	ret
spectranext_wifi_disconnect_fail:
	ld		hl, -1
	ret

; int8_t spectranext_gethostbyname(const char* hostname, uint32_t* result_ipv4); success: 0, error: -1.
; sccz80 LTR: top after ret = result_ipv4, then hostname. ROM: HL = hostname, DE = result_ipv4.
spectranext_gethostbyname:
	pop		bc
	pop		de		; result_ipv4 (2nd param)
	pop		hl		; hostname (1st param)
	push	bc

	push	ix
	ld		a, CMD_DNS
	IXCALL	SPECTRANEXT
	pop		ix
	jr		c, spectranext_gethostbyname_fail
	ld		hl, 0
	ret
spectranext_gethostbyname_fail:
	ld		hl, -1
	ret

; int8_t spectranext_enginecall(const char *input, const char *output, const char *operation);
; sccz80: top after ret = operation, then output, then input. ROM: HL=input, DE=output, BC=operation.
spectranext_enginecall:
	pop		af
	pop		de		; operation (3rd / top)
	push		de
	pop		bc		; BC = operation
	pop		de		; output (2nd)
	pop		hl		; input (1st)
	push		af

	push		ix
	ld		a, CMD_ENGINECALL
	IXCALL		SPECTRANEXT
	pop		ix
	jr		c, spectranext_enginecall_fail
	ld		hl, 0
	ret
spectranext_enginecall_fail:
	ld		l, a
	ld		h, 0
	bit		7, a
	jr		z, spectranext_enginecall_ret
	dec		h
spectranext_enginecall_ret:
	ret

; int32_t spectranext_xfs_read(const spectranext_xfs_read_request_t *request);
; __FASTCALL__: HL points to the packed 139-byte request. ROM returns the
; actual byte count in DEHL, which is also z88dk's 32-bit return convention.
spectranext_xfs_read:
	push	ix
	ld		a, CMD_XFS_READ
	IXCALL	SPECTRANEXT
	pop	ix
	jr	c, spectranext_xfs_read_fail
	ret
spectranext_xfs_read_fail:
	ld	de, -1
	ld		hl, -1
	ret
