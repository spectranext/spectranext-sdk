#include <stdio.h>
#include <sys/socket.h>
#include <spectranet.h>
#include <http.h>
#include <malloc.h>

// Initialize heap for malloc (required by httplib)
long heap = 0;
char heap_data[4096];

int main()
{
    // Page in Spectranext memory
    pagein();

    sbrk(heap_data, sizeof(heap_data));

    printf("Making HTTPS request to Cloudflare...\n");

    // Set up URI structure
    URI uri = {
        .proto = PROTO_HTTP,              // Protocol (HTTP/HTTPS)
        .host = "www.cloudflare.com",     // Hostname
        .port = 443,                       // HTTPS port (automatically enables TLS)
        .location = "/cdn-cgi/trace",     // Path on server
        .user = NULL,                      // Username (for HTTP auth, if needed)
        .passwd = NULL                    // Password (for HTTP auth, if needed)
    };

    // Make GET request - returns socket file descriptor
    int sockfd = request(GET, &uri);

    if (sockfd < 0)
    {
        printf("Failed to make request: %d\n", sockfd);
        printf("Error codes: EHTTP_SOCKFAIL=%d, EHTTP_DNSFAIL=%d, EHTTP_CONNFAIL=%d\n",
               EHTTP_SOCKFAIL, EHTTP_DNSFAIL, EHTTP_CONNFAIL);
        return 1;
    }

    printf("Request sent, reading headers...\n");

    // Read HTTP response headers
    int http_code;
    int code = readHeaders(sockfd, &http_code);

    if (code < 0)
    {
        printf("Failed to read headers: %d\n", code);
        sockclose(sockfd);
        freeheaders();
        return 1;
    }

    printf("HTTP Status Code: %d\n", http_code);
    printf("Response body:\n");

    // Read response data
    char rxbuf[512];
    int totalbytes = 0;
    int bytes;

    while ((bytes = readData(sockfd, rxbuf, sizeof(rxbuf) - 1)) > 0)
    {
        rxbuf[bytes] = '\0';  // Null-terminate for printing
        printf("%s", rxbuf);
        totalbytes += bytes;
    }

    printf("\n\nTotal bytes received: %d haha!\n", totalbytes);

    // Clean up
    sockclose(sockfd);
    freeheaders();

    printf("Done!\n");

    pageout();

    return 0;
}
