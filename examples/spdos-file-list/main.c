#include <stdio.h>
#include <string.h>
#include <spdos.h>
#include <spectranet.h>

int main(void)
{
    pagein();

    printf("SPDOS File List Example\n");
    printf("Listing files...\n\n");

    // RAMFS is available at mount point 0 by default
    // No need to mount anything
    setmountpoint(0);

    // List directory contents
    printf("Directory listing:\n");
    int dirhandle = opendir(".");
    if (dirhandle < 0) {
        printf("Failed to open directory\n");
        pageout();
        return 1;
    }

    static char dirbuf[256];
    int file_count = 0;
    int dir_count = 0;

    while (readdir(dirhandle, dirbuf) == 0) {
        char full_path[512];
        strncpy(full_path, dirbuf, sizeof(full_path) - 1);
        full_path[sizeof(full_path) - 1] = '\0';

        if (isdir(full_path)) {
            dir_count++;
            printf("  [DIR]  %s\n", dirbuf);
        } else {
            file_count++;
            printf("  [FILE] %s", dirbuf);

            // Get file size using stat
            static unsigned char statbuf[256];
            struct stat* st = (struct stat*)statbuf;
            unsigned long file_size = 0;
            if (stat(full_path, st) == 0) {
                file_size = *(unsigned long*)(statbuf + 6); // STAT_SIZE offset
                printf(" (%lu bytes)", file_size);
            }
            printf("\n");
        }
    }

    closedir(dirhandle);
    printf("\nFound %d file(s) and %d directory/directories\n\n", file_count, dir_count);

    // Now load boot.zx and display first 16 bytes as hex
    printf("Loading boot.zx...\n");
    int fd = open("boot.zx", O_RDONLY, 0);
    if (fd < 0) {
        printf("Failed to open boot.zx: %d\n", fd);
        pageout();
        return 1;
    }

    printf("Reading first 16 bytes...\n");
    static unsigned char buffer[16];
    ssize_t bytes_read = read(fd, buffer, 16);
    if (bytes_read < 0) {
        printf("Failed to read from boot.zx: %d\n", (int)bytes_read);
        close(fd);
        pageout();
        return 1;
    }

    close(fd);

    // Display bytes as hex
    printf("\nFirst %d bytes (hex):\n", (int)bytes_read);
    for (ssize_t i = 0; i < bytes_read; i++) {
        printf("%02x ", buffer[i]);
        if ((i + 1) % 8 == 0) {
            printf("\n");
        }
    }
    if (bytes_read % 8 != 0) {
        printf("\n");
    }

    printf("\nExample completed successfully\n");

    while (1) ;

    return 0;
}
