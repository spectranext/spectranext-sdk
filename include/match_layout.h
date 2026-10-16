#ifndef SPX_MATCH_LAYOUT_H
#define SPX_MATCH_LAYOUT_H
#include <stdint.h>
#define SPX_MATCH_IP 0xc6120001u /* 198.18.0.1: synthetic benchmark-range marker */
#define SPECTRANEXT_CMD_MATCHMAKING_MATCH 16
#define SPECTRANEXT_CMD_MATCHMAKING_GET_PEER 17
#define SPECTRANEXT_CMD_MATCHMAKING_CONNECT 18
#define SPECTRANEXT_CMD_MATCHMAKING_SET_NAME 19
#define SPECTRANEXT_CMD_MATCHMAKING_CODE 20
#define MATCH_MAX_PEERS 9
#define MATCH_PREPARING 0
#define MATCH_WAITING 1
#define MATCH_CONNECTING 2
#define MATCH_CONNECTED 3
#define MATCH_CANCELLED 4
#define MATCH_ERROR 5
/* Input and output share the mailbox. All multi-byte values are little endian.
 * module keeps its UI snapshot outside page B before issuing another command. */
#pragma pack(push, 1)
/** Module command input. socket is the W5100 index; action is command-specific
 * (MATCH: 0 poll/start, 1 cancel, other nonzero leave; CODE: enable boolean).
 * CONNECT/GET_PEER use zero-based index plus revision to reject stale rows.
 * text holds a bounded name/joining code; producers should NUL-terminate it. */
typedef struct {
    uint8_t socket, action, index;
    uint16_t revision;
    char text[24];
} match_request;
/** Peer identity and display data, not a network endpoint. device is the API
 * selection ID; name is display text; requires_code is boolean. Empty device
 * means an unused row. Strings include space for a terminating NUL. */
typedef struct {
    char device[65], name[24];
    uint8_t requires_code;
} match_peer;
/** Complete UI snapshot copied out of the shared mailbox before another call.
 * stage is MATCH_*; count is the highest occupied peer slot plus one (holes
 * may exist); revision changes with the peer table. code is empty or four
 * digits. peer is selected-peer info, or the indexed peer for GET_PEER. */
typedef struct {
    uint8_t stage, count;
    uint16_t revision;
    char name[24], code[5], service[65], error[32];
    match_peer peer;
} match_snapshot;
#pragma pack(pop)
#ifndef __SPECTRUM__
_Static_assert(sizeof(match_request) == 29, "Match request ABI");
_Static_assert(sizeof(match_snapshot) == 220, "Match snapshot ABI");
#endif
#endif
