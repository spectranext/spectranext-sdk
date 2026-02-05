#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <spectranet.h>
#include <spdos.h>

int main(void)
{
    pagein();

    printf("HTTPS copy example\n");
    printf("Mounting HTTPS filesystem at mount point 1...\n");
    
    // Mount HTTPS filesystem at mount point 1
    int mount_result = mount(1, NULL, NULL, "/test/https", "spectranext.net", "https");
    if (mount_result < 0) {
        printf("Failed to mount HTTPS filesystem\n");
        return 1;
    }
    
    printf("Opening 1:folder/file-d.bin for reading...\n");

    setmountpoint(1);
    
    // Open source file from HTTPS (mount point 1) using mount point prefix
    int src_fd = open("folder/file-d.bin", O_RDONLY, 0);
    if (src_fd < 0) {
        printf("Failed to open 1:folder/file-d.bin: %d\n", src_fd);
        umount(1);
        return 1;
    }
    
    printf("Opening 0:copy-d.bin for writing...\n");

    setmountpoint(0);
    
    // Open destination file in RAMFS (mount point 0) using mount point prefix
    int dst_fd = open("copy-d.bin", O_WRONLY | O_CREAT | O_TRUNC, 0);
    if (dst_fd < 0) {
        printf("Failed to open 0:copy-d.bin: %d\n", dst_fd);
        close(src_fd);
        umount(1);
        return 1;
    }
    
    printf("Copying data...\n");
    
    // Copy data in a loop
    static unsigned char buffer[256];
    int total_bytes = 0;
    ssize_t bytes_read;
    
    while ((bytes_read = read(src_fd, buffer, sizeof(buffer))) > 0) {
        ssize_t bytes_written = write(dst_fd, buffer, bytes_read);
        if (bytes_written < 0 || bytes_written != bytes_read) {
            printf("Write failed: wrote %d/%d\n", (int)bytes_written, (int)bytes_read);
            close(dst_fd);
            close(src_fd);
            umount(1);
            return 1;
        }
        total_bytes += bytes_read;
        printf("Copied %d bytes...\n", total_bytes);
    }
    
    if (bytes_read < 0) {
        printf("Read error: %d\n", (int)bytes_read);
        close(dst_fd);
        close(src_fd);
        umount(1);
        return 1;
    }
    
    printf("Copy complete: %d bytes\n", total_bytes);
    
    // Close files
    close(dst_fd);
    close(src_fd);

    printf("Copy example completed successfully\n");

    while (1) ;

    return 0;
}
