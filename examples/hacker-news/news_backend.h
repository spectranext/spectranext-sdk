#ifndef NEWS_BACKEND_H
#define NEWS_BACKEND_H

#include <stdint.h>

#include "zxgui.h"

#define NEWS_SELECT_BUFFER_SIZE 4096u
#define NEWS_SELECT_CAPACITY 16u
#define NEWS_ARTICLE_TITLE_MAX 256u
#define NEWS_ARTICLE_CONTENT_MAX 3072u
#define NEWS_ARTICLE_URL_MAX 512u

struct news_article_info {
    uint32_t id;
};

struct news_article_details {
    char title[NEWS_ARTICLE_TITLE_MAX];
    char content[NEWS_ARTICLE_CONTENT_MAX];
    char url[NEWS_ARTICLE_URL_MAX];
};

extern struct news_article_details s_article;

int news_backend_init(void);
void news_backend_shutdown(void);

int news_backend_fetch_latest(void);
int news_backend_fetch_article(uint32_t id, const char *title);
void news_backend_reset_select(struct gui_select_t *select);
int news_backend_fill_select(struct gui_select_t *select, uint8_t row_budget);

uint8_t *news_backend_select_buffer(void);
const struct news_article_info *news_backend_option_info(const struct gui_select_option_t *option);
const struct news_article_details *news_backend_current_article(void);

#endif
