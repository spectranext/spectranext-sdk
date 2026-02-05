#include <stdio.h>
#include <string.h>
#include <spdos.h>
#include <spectranet.h>

// Function to scan a directory and check entries
static int scan_directory(const char* dir_path)
{
    printf("\nScanning directory: %s\n", dir_path);
    
    // Open directory
    int dirhandle = opendir(dir_path);
    if (dirhandle < 0) {
        printf("Failed to open directory: %s\n", dir_path);
        return -1;
    }
    
    // Buffer for directory entries
    static char dirbuf[256];
    int file_count = 0;
    int dir_count = 0;
    
    // Read all directory entries
    while (readdir(dirhandle, dirbuf) == 0) {
        // Use stat to check if it's a directory
        char full_path[512];
        if (strcmp(dir_path, ".") == 0) {
            strncpy(full_path, dirbuf, sizeof(full_path) - 1);
            full_path[sizeof(full_path) - 1] = '\0';
        } else {
            snprintf(full_path, sizeof(full_path), "%s/%s", dir_path, dirbuf);
        }
        
        if (isdir(full_path)) {
            dir_count++;
            printf("  [DIR]  %s\n", dirbuf);
        } else {
            file_count++;
            printf("  [FILE] %s", dirbuf);
            
            // Try to read file size using stat
            static unsigned char statbuf[256];
            struct stat* st = (struct stat*)statbuf;
            unsigned long file_size = 0;
            if (stat(full_path, st) == 0) {
                unsigned short mode = *(unsigned short*)statbuf;
                file_size = *(unsigned long*)(statbuf + 6); // STAT_SIZE offset
                printf(" (%lu bytes)", file_size);
            }
            printf("\n");
            
            // Read and verify file contents (0-255 pattern)
            if (file_size > 0) {
                int fd = open(full_path, O_RDONLY, 0);
                if (fd >= 0) {
                    static unsigned char filebuf[256];
                    unsigned long total_read = 0;
                    int pattern_ok = 1;
                    
                    // Read file in 256-byte chunks and verify each chunk
                    while (total_read < file_size && pattern_ok) {
                        ssize_t bytes_read = read(fd, filebuf, 256);
                        if (bytes_read <= 0) {
                            printf("    ERROR: %d Failed to read at offset %lu\n", fd, total_read);
                            close(fd);
                            return -1;
                        }
                        
                        // Verify this chunk matches 0-255 pattern
                        for (ssize_t i = 0; i < bytes_read; i++) {
                            unsigned char expected = (unsigned char)((total_read + i) % 256);
                            if (filebuf[i] != expected) {
                                pattern_ok = 0;
                                printf("    ERROR: %d Pattern mismatch at offset %lu: expected %d, got %d\n", 
                                       fd, total_read + i, expected, filebuf[i]);
                                break;
                            }
                        }
                        
                        total_read += bytes_read;
                    }
                    
                    close(fd);
                    
                    if (pattern_ok && total_read == file_size) {
                        printf("    %d Pattern verified (0-255 repeating, %lu bytes)\n", fd, total_read);
                    } else if (pattern_ok) {
                        printf("    ERROR: %d Read %lu bytes but file size is %lu\n", fd, total_read, file_size);
                        return -1;
                    } else {
                        printf("    ERROR: %d Pattern verification failed\n", fd);
                        return -1;
                    }
                } else {
                    printf("    ERROR: Failed to open file for reading\n");
                    return -1;
                }
            }
        }
    }
    
    closedir(dirhandle);
    
    printf("Found %d file(s) and %d directory/directories\n", file_count, dir_count);
    
    return 0;
}

int main(void)
{
    pagein();

    printf("Unmounting filesystem...\n");

    printf("Mounting https://spectranext.net/test/https...\n");
    
    // Mount HTTPS filesystem
    // mount(mount_point, password, user_id, path, hostname, protocol)
    int mount_result = mount(1, NULL, NULL, "/test/https", "spectranext.net", "https");
    if (mount_result) {
        printf("Failed to mount HTTPS filesystem\n");
        return 1;
    }
    
    printf("Mount successful. Setting mount point...\n");
    
    // Set mount point 1 as active
    if (setmountpoint(1) < 0) {
        printf("Failed to set mount point\n");
        return 1;
    }
    
    // Scan current directory "."
    if (scan_directory(".") < 0) {
        umount(1);
        return 1;
    }
    
    // Scan "folder" subdirectory if it exists
    static unsigned char statbuf[256];
    struct stat* st = (struct stat*)statbuf;
    if (stat("folder", st) == 0) {
        unsigned short mode = *(unsigned short*)statbuf;
        if ((mode & S_IFDIR) != 0) {
            // It's a directory, scan it
            if (scan_directory("folder") < 0) {
                umount(1);
                return 1;
            }
        }
    } else {
        printf("\nDirectory 'folder' not found\n");
        umount(1);
        return 1;
    }
    
    printf("\nDirectory scan completed!\n");

    while (1) ;

    return 0;
}
