#ifndef SPECTRANEXT_STRINGS_H
#define SPECTRANEXT_STRINGS_H
#include <stdint.h>
#define SPECTRANEXT_CMD_GET_STRING 21
/* GET_STRING mailbox request: u8 string_id, u8 capacity (including NUL).
 * Success replaces workspace with the NUL-terminated string; failure returns
 * status 1 and an empty string. Capacity zero never writes the caller buffer.
 * VERSION is served by the shared Z80 controller ROM rather than the mailbox. */
enum spectranext_string_t {
    SPECTRANEXT_STRING_SERIAL = 0,
    SPECTRANEXT_STRING_VERSION = 1,
    SPECTRANEXT_STRING_MATCH_NAME = 2,
    SPECTRANEXT_STRING_MATCH_PEER_SERIAL = 3,
    SPECTRANEXT_STRING_MATCH_PEER_NAME = 4,
    SPECTRANEXT_STRING_MATCH_INITIATOR_SERIAL = 5
};
#endif
