#ifndef SPDOS_H
#define SPDOS_H

#include <fcntl.h>
#include <sys/types.h>

/* DOS-compatible filesystem functions forwarding to Spectranet VFS */

/* File operations */
int open(char *name, int flags, mode_t mode);
int close(int handle);
ssize_t read(int handle, void *buf, size_t len);
ssize_t write(int handle, void *buf, size_t len);
int readbyte(int fd);
int writebyte(int handle, int c);
long lseek(int fd, long posn, int whence);

/* Directory operations */
int mkdir(char *name);
int rmdir(char *name);
int chdir(char *name);
char *getcwd(char *buf, size_t buflen);

/* File management */
int rename(const char *s, const char *d);
int remove(char *name);
int unlink(char *name);

/* Directory reading */
int opendir(char *name);
int readdir(int dirhandle, void *buf);
int closedir(int dirhandle);

/* Mount operations (Spectranet-specific) */
int mount(int mount_point, char *path);
int umount(int mount_point);

#endif /* SPDOS_H */

