#include <fcntl.h>
#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include <spectranet.h>
#include <spdos.h>
#include <spectranext.h>

#include "news_backend.h"

#define HTTPS_MOUNT 3
#define RAM_MOUNT 0
#define NEWS_BIN_PATH "news.bin"
#define ARTICLE_BIN_PATH "article.bin"
#define NEWS_FIELD_LEN 256u
#define ARTICLE_PATH_LEN 32u

extern ssize_t read(int fd, void *buf, size_t count);

static uint8_t s_select_buffer[NEWS_SELECT_BUFFER_SIZE];
struct news_article_details s_article;
static int s_fd = -1;
static int s_rows_total;
static int s_rows_loaded;

static const uint8_t s_empty_icon[8] = {0, 0, 0, 0, 0, 0, 0, 0};

static int read_le_string(int fd, char *buf, size_t buf_sz)
{
    uint8_t le[2];
    uint16_t n;

    if (read(fd, le, 2) != 2) {
        printf("[backend] read_le_string failed to read length fd=%d errno=%d\n", fd, errno);
        return -1;
    }

    n = (uint16_t)(le[0] | (uint16_t)(le[1] << 8));
    if (n == 0u || n > buf_sz) {
        printf("[backend] read_le_string invalid len=%u buf_sz=%u fd=%d\n",
            (unsigned)n, (unsigned)buf_sz, fd);
        return -1;
    }
    if (read(fd, buf, n) != (ssize_t)n) {
        printf("[backend] read_le_string payload read failed len=%u fd=%d errno=%d\n",
            (unsigned)n, fd, errno);
        return -1;
    }
    return 0;
}

static void close_stream(void)
{
    if (s_fd >= 0) {
        printf("[backend] close stream fd=%d\n", s_fd);
        close(s_fd);
        s_fd = -1;
    }
}

static int open_stream(void)
{
    char count_buf[16];
    int total_scalars;

    if (s_fd >= 0) {
        return 0;
    }

    setmountpoint(RAM_MOUNT);
    s_fd = open(NEWS_BIN_PATH, O_RDONLY, 0);
    if (s_fd < 0) {
        printf("[backend] open_stream open '%s' failed errno=%d\n", NEWS_BIN_PATH, errno);
        return -1;
    }
    printf("[backend] open_stream opened '%s' fd=%d\n", NEWS_BIN_PATH, s_fd);

    if (read_le_string(s_fd, count_buf, sizeof(count_buf)) != 0) {
        printf("[backend] open_stream failed reading total count\n");
        close_stream();
        return -1;
    }

    total_scalars = atoi(count_buf);
    if (total_scalars < 0) {
        printf("[backend] open_stream invalid total_scalars='%s'\n", count_buf);
        close_stream();
        return -1;
    }

    s_rows_total = total_scalars / 2;
    s_rows_loaded = 0;
    printf("[backend] open_stream total_scalars=%d rows_total=%d\n", total_scalars, s_rows_total);
    return 0;
}

int news_backend_init(void)
{
    int rc;

    printf("[backend] init mount=%d host=api.hnpwa.com path=/v0\n", HTTPS_MOUNT);
    rc = mount(HTTPS_MOUNT, NULL, NULL, "/v0", "api.hnpwa.com", "https");
    if (rc < 0) {
        printf("[backend] mount failed rc=%d errno=%d\n", rc, errno);
        return -1;
    }
    printf("[backend] mount ok rc=%d\n", rc);
    return 0;
}

void news_backend_shutdown(void)
{
    printf("[backend] shutdown\n");
    close_stream();
    umount(HTTPS_MOUNT);
}

int news_backend_fetch_latest(void)
{
    int rc;

    close_stream();
    printf("[backend] fetch_latest src='3:show/1.json' dst='%s' query=%s\n",
        NEWS_BIN_PATH,
        "json '$[*][\"id\",\"title\"]'");

    rc = spectranext_enginecall(
            "3:show/1.json",
            NEWS_BIN_PATH,
            "json '$[*][\"id\",\"title\"]'");
    if (rc != 0) {
        printf("[backend] fetch_latest enginecall failed rc=%d errno=%d\n", rc, errno);
        return -1;
    }
    printf("[backend] fetch_latest enginecall ok\n");

    s_rows_total = 0;
    s_rows_loaded = 0;
    return 0;
}

int news_backend_fetch_article(uint32_t id, const char *title)
{
    char item_path[ARTICLE_PATH_LEN];
    char count_buf[16];
    int fd;
    int rc;

    close_stream();
    printf("[backend] fetch_article id=%lu title='%s'\n", (unsigned long)id, title ? title : "(null)");

    strncpy(s_article.title, title ? title : "", sizeof(s_article.title) - 1u);
    s_article.title[sizeof(s_article.title) - 1u] = '\0';
    s_article.content[0] = '\0';
    s_article.url[0] = '\0';

    sprintf(item_path, "3:item/%lu.json", (unsigned long)id);
    printf("[backend] fetch_article src='%s' dst='%s' query=%s\n",
        item_path,
        ARTICLE_BIN_PATH,
        "json '$.content' '$.url'");
    rc = spectranext_enginecall(
            item_path,
            ARTICLE_BIN_PATH,
            "json '$.content' '$.url'");
    if (rc != 0) {
        printf("[backend] fetch_article enginecall failed rc=%d errno=%d src='%s'\n",
            rc, errno, item_path);
        return -1;
    }
    printf("[backend] fetch_article enginecall ok\n");

    setmountpoint(RAM_MOUNT);
    fd = open(ARTICLE_BIN_PATH, O_RDONLY, 0);
    if (fd < 0) {
        printf("[backend] fetch_article open '%s' failed errno=%d\n", ARTICLE_BIN_PATH, errno);
        return -1;
    }
    printf("[backend] fetch_article opened '%s' fd=%d\n", ARTICLE_BIN_PATH, fd);

    if (read_le_string(fd, count_buf, sizeof(count_buf)) != 0 ||
        read_le_string(fd, s_article.content, sizeof(s_article.content)) != 0 ||
        read_le_string(fd, count_buf, sizeof(count_buf)) != 0 ||
        read_le_string(fd, s_article.url, sizeof(s_article.url)) != 0) {
        printf("[backend] fetch_article failed while decoding '%s'\n", ARTICLE_BIN_PATH);
        close(fd);
        return -1;
    }

    printf("[backend] queried article content='%s' url='%s'\n",
        s_article.content, s_article.url);

    close(fd);

    if (s_article.content[0] == '\0') {
        strncpy(s_article.content, "(no content)", sizeof(s_article.content) - 1u);
        s_article.content[sizeof(s_article.content) - 1u] = '\0';
    }
    printf("[backend] article normalized content='%s' url='%s'\n",
        s_article.content, s_article.url);

    return 0;
}

void news_backend_reset_select(struct gui_select_t *select)
{
    printf("[backend] reset_select\n");
    memset(s_select_buffer, 0, sizeof(s_select_buffer));
    close_stream();
    s_rows_total = 0;
    s_rows_loaded = 0;

    select->buffer_offset = select->options_capacity * sizeof(struct gui_select_option_t *);
    select->selection = 0u;
    select->last_selection = 0u;
    select->options_size = 0u;
    select->base.flags |= GUI_FLAG_DIRTY;
}

int news_backend_fill_select(struct gui_select_t *select, uint8_t row_budget)
{
    char id_buf[16];
    char title_buf[NEWS_FIELD_LEN];
    uint8_t before;

    if (open_stream() != 0) {
        printf("[backend] fill_select open_stream failed\n");
        return -1;
    }

    before = select->options_size;
    printf("[backend] fill_select start budget=%u rows_loaded=%d rows_total=%d options=%u\n",
        row_budget, s_rows_loaded, s_rows_total, before);

    while (row_budget != 0u && s_rows_loaded < s_rows_total && select->options_size < select->options_capacity) {
        uint8_t title_len;
        uint16_t needed;
        struct news_article_info *info;

        if (read_le_string(s_fd, id_buf, sizeof(id_buf)) != 0 ||
            read_le_string(s_fd, title_buf, sizeof(title_buf)) != 0) {
            printf("[backend] fill_select failed reading row at loaded=%d\n", s_rows_loaded);
            close_stream();
            return -1;
        }

        title_len = (uint8_t)strlen(title_buf);
        needed = (uint16_t)(sizeof(struct gui_select_option_t) + title_len + 1u + sizeof(struct news_article_info));
        if ((uint16_t)select->buffer_offset + needed > NEWS_SELECT_BUFFER_SIZE) {
            printf("[backend] fill_select buffer full offset=%u needed=%u cap=%u\n",
                (unsigned)select->buffer_offset, (unsigned)needed, (unsigned)NEWS_SELECT_BUFFER_SIZE);
            close_stream();
            return 0;
        }

        info = (struct news_article_info *)zxgui_select_add_option(
            select,
            title_buf,
            title_len,
            sizeof(struct news_article_info),
            (uint8_t *)s_empty_icon,
            0u);
        if (!info) {
            printf("[backend] fill_select zxgui_select_add_option returned NULL\n");
            close_stream();
            return 0;
        }

        info->id = (uint32_t)strtoul(id_buf, NULL, 10);
        printf("[backend] fill_select row=%d id=%lu title='%s'\n",
            s_rows_loaded,
            (unsigned long)info->id,
            title_buf);

        s_rows_loaded++;
        row_budget--;
        select->base.flags |= GUI_FLAG_DIRTY;
    }

    if (s_rows_loaded >= s_rows_total || select->options_size >= select->options_capacity) {
        printf("[backend] fill_select finished rows_loaded=%d rows_total=%d options=%u capacity=%u\n",
            s_rows_loaded, s_rows_total, select->options_size, select->options_capacity);
        close_stream();
        return 0;
    }

    printf("[backend] fill_select partial rows_loaded=%d rows_total=%d options=%u\n",
        s_rows_loaded, s_rows_total, select->options_size);
    return 1;
}

uint8_t *news_backend_select_buffer(void)
{
    return s_select_buffer;
}

const struct news_article_info *news_backend_option_info(const struct gui_select_option_t *option)
{
    return (const struct news_article_info *)option->user;
}

const struct news_article_details *news_backend_current_article(void)
{
    return &s_article;
}
