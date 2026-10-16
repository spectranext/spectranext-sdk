#ifndef __SOCKET_H__
#define __SOCKET_H__

/*
 * socket.h
 *
 * Routines that call the Spectranet ROM socket library.
 *
 * 2008-05-03 Dylan Smith
 */

/* Definitions */
#define AF_INET		0
#define SOCK_STREAM	1
#define SOCK_DGRAM	2
#define SOCK_RAW	3

/*
 * Spectranext stream backends. These values are passed in socket()'s
 * protocol argument and are valid only with AF_INET + SOCK_STREAM.
 *
 * A value of zero retains the historical plain TCP behaviour. These values
 * deliberately use both bytes of socket()'s protocol argument. Direct ROM
 * callers must initialise DE: D=0xFF enables the selector in E; use DE=0 for
 * ordinary TCP. The C socket() wrappers load DE from protocol explicitly.
 */
#define SPECTRANET_PROTO_TCP	0x0000
#define SPECTRANET_PROTO_TLS	0xFFF0
#define SPECTRANET_PROTO_SSH	0xFFF1
#define SPECTRANET_PROTO_GRE_TCP	0xFFF2

/* Much of this should ultimately end up in sys/types.h */
#define in_addr_t	unsigned long

/* Structures */

struct in_addr
{
	in_addr_t s_addr;		/* 32 bits */
};

/* As defined in http://tools.ietf.org/html/draft-ietf-sip-bsd-systems-00 */
struct sockaddr_in	/* internet socket address structure */
{
	int sin_family;			/* offset 0 */
	unsigned int sin_port;		/* offset 2 */
	struct in_addr sin_addr;	/* offset 4 */
	char sin_zero[8];		/* offset 8 */
};

#define sockaddr sockaddr_in
#define socklen_t int

/* CALLER and FASTCALL linkage calls */
/**
 * Allocate an AF_INET socket of type SOCK_STREAM or SOCK_DGRAM. protocol selects
 * the supported backend (0 for ordinary TCP). Return descriptor or -1 on error.
 * The caller owns the descriptor and must sockclose it after use.
 */
extern int __LIB__	socket(int domain, int type, int protocol);
/**
 * Close and release fd. Return the ROM result, -1 on error.
 * Do not use the descriptor afterward; this does not free application buffers.
 */
extern int __LIB__ __FASTCALL__ sockclose(int fd);
/**
 * Bind sockfd to the local address in my_addr (addrlen bytes).
 * The SDK uses its native IPv4/port representation. Return 0 on success or -1
 * on error. The address is borrowed and not retained.
 */
extern int __LIB__	bind(int sockfd, struct sockaddr *my_addr, socklen_t addrlen);
/**
 * Connect sockfd to serv_addr (addrlen bytes), blocking until setup finishes.
 * For a resolved @match.spx marker, opens the system menu and returns only
 * after matching/transport setup or cancellation. Both matched programs call
 * connect. Return 0 on success or -1 on failure; caller must close on failure.
 */
extern int __LIB__	connect(int sockfd, struct sockaddr *serv_addr, socklen_t addrlen);
/**
 * Send up to len bytes from borrowed buf on a connected stream.
 * Return bytes accepted, possibly fewer than requested, or -1 on error.
 * flags follows ROM support; caller must handle partial writes and framing.
 */
extern int __LIB__	send(int sockfd, void *buf, int len, int flags);
/**
 * Receive up to len bytes into caller-owned buf on a connected stream.
 * Return the ROM byte count or -1 on error; reads can be partial and are not
 * application message boundaries. flags follows the underlying ROM API.
 */
extern int __LIB__	recv(int sockfd, void *buf, int len, int flags);
/**
 * Wait for a connection on listening sockfd and return its connected descriptor
 * or -1 on failure. addr/addrlen are caller-owned peer-address output storage.
 * The caller must close the accepted descriptor. Not needed for matchmaking.
 */
extern int __LIB__	accept(int sockfd, struct sockaddr *addr, socklen_t *addrlen);
/**
 * Put sockfd into listening mode using the ROM's backlog semantics.
 * Return 0 on success or -1 on error; use accept to obtain a connection.
 * Not needed for matchmaking, where both endpoints call connect.
 */
extern int __LIB__	listen(int sockfd, int backlog);

/* CALLEE linkage calls */
/**
 * Callee-linkage entry for socket; same arguments, ownership, blocking, and
 * return contract as socket. Normally selected by the public function macro.
 */
extern int __LIB__ __CALLEE__	socket_callee(int domain, int type, int proto);
/**
 * Callee-linkage entry for bind; same arguments, ownership, blocking, and
 * return contract as bind. Normally selected by the public function macro.
 */
extern int __LIB__ __CALLEE__	bind_callee(int sockfd, struct sockaddr *my_addr, socklen_t addrlen);
/**
 * Callee-linkage entry for connect; same arguments, ownership, blocking, and
 * return contract as connect. Normally selected by the public function macro.
 */
extern int __LIB__ __CALLEE__	connect_callee(int sockfd, struct sockaddr *serv_addr, socklen_t addrlen);
/**
 * Callee-linkage entry for send; same arguments, ownership, blocking, and
 * return contract as send. Normally selected by the public function macro.
 */
extern int __LIB__ __CALLEE__	send_callee(int sockfd, void *buf, int len, int flags);
/**
 * Send one datagram of len bytes from buf to the borrowed to address (tolen
 * bytes). Return the ROM byte count or -1 on error. flags follows ROM support;
 * for a matchmade UDP socket retain/use the destination from its hostname lookup.
 * Callee-linkage target of sendto; caller retains all buffers.
 */
extern int __LIB__ __CALLEE__ 	sendto_callee(int sockfd, void *buf, int len, int flags, struct sockaddr *to, socklen_t tolen);
/**
 * Callee-linkage entry for recv; same arguments, ownership, blocking, and
 * return contract as recv. Normally selected by the public function macro.
 */
extern int __LIB__ __CALLEE__	recv_callee(int sockfd, void *buf, int len, int flags);
/**
 * Receive one datagram into caller-owned buf[len] and write its source address
 * to from/fromlen. Return the ROM byte count or -1 on error. A short buffer
 * discards the unread datagram remainder; flags follows ROM support.
 * Callee-linkage target of recvfrom; no buffer ownership transfer.
 */
extern int __LIB__ __CALLEE__	recvfrom_callee(int sockfd, void *buf, int len, int flags, struct sockaddr *from, socklen_t *fromlen);
/**
 * Callee-linkage entry for accept; same arguments, ownership, blocking, and
 * return contract as accept. Normally selected by the public function macro.
 */
extern int __LIB__ __CALLEE__	accept_callee(int sockfd, struct sockaddr *addr, socklen_t *addrlen);
/**
 * Callee-linkage entry for listen; same arguments, ownership, blocking, and
 * return contract as listen. Normally selected by the public function macro.
 */
extern int __LIB__ __CALLEE__	listen_callee(int sockfd, int backlog);

/* Make CALLEE default */
#define socket(a,b,c)		socket_callee(a,b,c)
#define bind(a,b,c)		bind_callee(a,b,c)
#define connect(a,b,c)		connect_callee(a,b,c)
#define send(a,b,c,d)		send_callee(a,b,c,d)
#define sendto(a,b,c,d,e,f)	sendto_callee(a,b,c,d,e,f)
#define recv(a,b,c,d)		recv_callee(a,b,c,d)
#define recvfrom(a,b,c,d,e,f)	recvfrom_callee(a,b,c,d,e,f)
#define accept(a,b,c)		accept_callee(a,b,c)
#define listen(a,b)		listen_callee(a,b)

/* htons is a no-op, since all the calls convert machine byte order to
 * network byte order. The macro is provided for compatibility */
#define htons(a)		(a)
#define ntohs(a)		(a)

#endif
