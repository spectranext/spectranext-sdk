#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <spectranet.h>

int main()
{
    // Page in Spectranext memory
    pagein();

    printf("Opening file: data.txt\n");

    // Open file for reading using open() from spdos.h
    // Works with any mounted filesystem (XFS, TNFS, etc.)
    // O_RDONLY = read only, O_WRONLY = write only, O_CREAT = create if missing
    int fd = open("data.txt", O_RDONLY, 0);
    if (fd < 0)
    {
        printf("Failed to open file\n");
        return 1;
    }

    printf("File opened successfully\n");
    printf("Reading file contents...\n");

    // Read file data using read()
    char buffer[256];
    ssize_t bytes_read = read(fd, buffer, sizeof(buffer) - 1);

    if (bytes_read <= 0)
    {
        printf("Failed to read file or file is empty\n");
        close(fd);
        return 1;
    }

    // Null-terminate the buffer for printing
    buffer[bytes_read] = '\0';

    printf("Read %d bytes:\n", (int)bytes_read);
    printf("%s\n", buffer);

    // Close file using close()
    close(fd);
    printf("File closed\n");

    pageout();

    return 0;
}
