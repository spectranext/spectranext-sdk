#ifndef _SPECTRANEXT_H_
#define _SPECTRANEXT_H_

#include <stdint.h>

#define SPECTRANEXT_STATUS_IN_PROGRESS (0xFFu)
#define SPECTRANEXT_STATUS_SUCCESS (0u)
#define SPECTRANEXT_STATUS_ERROR (1u)
#define SPECTRANEXT_XFS_READ_PATH_MAX (128u)
#define SPECTRANEXT_VERSION_SIZE (32u)

#if defined(__SPECTRUM__)
#define SPECTRANEXT_PACKED
#else
#define SPECTRANEXT_PACKED __attribute__((packed))
#endif

typedef struct SPECTRANEXT_PACKED spectranext_xfs_read_request_s
{
    char source_filename[SPECTRANEXT_XFS_READ_PATH_MAX];
    uint32_t source_offset;
    uint8_t target_first_page;
    uint16_t target_first_page_offset;
    uint32_t maximum_data;
} spectranext_xfs_read_request_t;

typedef struct SPECTRANEXT_PACKED spectranext_wifi_scan_result_s
{
    char ssid[64];
    uint8_t bssid[6];
    int8_t rssi;
} spectranext_wifi_scan_result_t;

#undef SPECTRANEXT_PACKED

enum spectranext_cmd_t
{
    SPECTRANEXT_CMD_GET_CONTROLLER_STATUS = 0,
    SPECTRANEXT_CMD_WIFI_SCAN_ACCESS_POINTS = 1,
    SPECTRANEXT_CMD_WIFI_GET_ACCESS_POINT = 2,
    SPECTRANEXT_CMD_WIFI_CONNECT_ACCESS_POINT = 3,
    SPECTRANEXT_CMD_WIFI_DISCONNECT = 4,
    SPECTRANEXT_CMD_DNS_GETHOSTBYNAME = 5,
    SPECTRANEXT_CMD_ENGINECALL = 6,
    SPECTRANEXT_CMD_GET_MESSAGE = 7,
    SPECTRANEXT_CMD_XFS_READ = 8,
    CMD_SYS_SETTINGS_READ = 9,
    CMD_SYS_SETTINGS_WRITE = 10,
    CMD_SYS_DIAGNOSTICS = 11,
    CMD_SYS_UPGRADE = 12,
    SPECTRANEXT_CMD_GET_VERSION = 15
};

#define SPECTRANEXT_SETTINGS_SIZE 16u
#define SPECTRANEXT_SETTINGS_DIVMMC_OFFSET 0u
#define SPECTRANEXT_SAFETY_BOOTLOADER_VERSION 3u

#define WIFI_CONTROLLER_STATUS_OFFLINE (0u)
#define WIFI_CONTROLLER_STATUS_BUSY_UPDATING (1u)
#define WIFI_CONTROLLER_STATUS_OPERATIONAL (2u)

#define WIFI_SCAN_NONE (0)
#define WIFI_SCAN_SCANNING (1)
#define WIFI_SCAN_COMPLETE (2)
#define WIFI_SCAN_FAILURE (-1)

#define WIFI_CONNECT_DISCONNECTED (0)
#define WIFI_CONNECT_CONNECTING (1)
#define WIFI_CONNECT_CONNECT_SUCCESS (2)
#define WIFI_CONNECT_CONNECT_IP_OBTAINED (3)

#define GETHOSTBYNAME_STATUS_NONE (0)
#define GETHOSTBYNAME_STATUS_SUCCESS (1)
#define GETHOSTBYNAME_STATUS_HOST_NOT_FOUND (-1)
#define GETHOSTBYNAME_STATUS_TIMEOUT (-2)
#define GETHOSTBYNAME_STATUS_SYSTEM_FAILURE (-3)

#ifdef __SPECTRUM__
extern int __LIB__ __FASTCALL__ spectranext_detect(void);
/* Buffers must be outside page B (2000-2fff), including their full range.
 * READ returns length 16; WRITE returns 0. Errors return negative settings
 * error codes. No-page WRITE callers must page out from host RAM after return.
 */
extern int16_t __LIB__ spectranext_settings_read(uint8_t *payload, uint16_t capacity) __z88dk_callee;
extern int16_t __LIB__ spectranext_settings_write(const uint8_t *payload, uint16_t length) __z88dk_callee;
/* 10 bytes: bootloader u32 LE, active policy u8, lock reason u32 LE,
 * bootloader safety support u8. */
extern int16_t __LIB__ __FASTCALL__ spectranext_get_diagnostics(uint8_t *out);
extern int16_t __LIB__ spectranext_upgrade(void) __z88dk_callee;

/**
 * All functions below return **-1** on ROM/port failure (distinct from valid non‑negative results;
 * e.g. Wi‑Fi scan can return count **1** on success).
 * On success: get_controller_status returns **controller_status** (>=0); scan returns **scan_count** (>=0);
 * the others return **0**.
 */
extern int8_t __LIB__ spectranext_get_controller_status(int8_t *wifi_connection_out, uint32_t *ipv4_out) __z88dk_callee;
/* Writes a NUL-terminated build version to 32 bytes outside page B. */
extern int8_t __LIB__ __FASTCALL__ spectranext_get_version(char *version_out);
extern int8_t __LIB__ spectranext_wifi_scan_access_points(void) __z88dk_callee;
extern int8_t __LIB__ spectranext_wifi_get_access_point(uint8_t ap, spectranext_wifi_scan_result_t *result) __z88dk_callee;
extern int8_t __LIB__ spectranext_wifi_connect_access_point(const char *ssid, const char *password,
    const uint8_t *bssid) __z88dk_callee;
extern int8_t __LIB__ spectranext_wifi_disconnect(void) __z88dk_callee;
extern int8_t __LIB__ spectranext_gethostbyname(const char *hostname, uint32_t *result_ipv4) __z88dk_callee;
/**
 * `input` must name a file as **"N:path"** where **N** is the XFS mount index (0..3) and **path** is relative
 * to that mount (e.g. `"1:data.json"`). `output` is always written to the **RAM** XFS volume (plain path, no prefix).
 * On success returns 0; on failure a negative engine error code.
 */
extern int8_t __LIB__ spectranext_enginecall(const char *input, const char *output, const char *operation) __z88dk_callee;
/**
 * Read an XFS file range into controller RAM according to `request`.
 * Returns the actual number of bytes read, or -1 on controller/XFS failure.
 */
extern int32_t __LIB__ __FASTCALL__ spectranext_xfs_read(const spectranext_xfs_read_request_t *request);
#endif

#endif
