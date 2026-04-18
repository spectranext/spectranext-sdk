#include <arch/zx/spectrum.h>
#include <stdio.h>
#include <string.h>

#include "app.h"
#include "news_backend.h"
#include "ui.h"

enum app_phase_t {
    APP_PHASE_SPLASH = 0,
    APP_PHASE_FETCH_LATEST,
    APP_PHASE_FILL_LATEST,
    APP_PHASE_FETCH_ARTICLE,
    APP_PHASE_READY,
    APP_PHASE_ERROR
};

static enum app_phase_t s_phase;
static enum app_phase_t s_phase_after_splash;
static uint8_t s_selection_ready;
static const struct news_article_info *s_pending_article_info;
static char s_pending_article_title[NEWS_ARTICLE_TITLE_MAX];

static const char *phase_name(enum app_phase_t phase)
{
    switch (phase) {
    case APP_PHASE_SPLASH:
        return "SPLASH";
    case APP_PHASE_FETCH_LATEST:
        return "FETCH_LATEST";
    case APP_PHASE_FILL_LATEST:
        return "FILL_LATEST";
    case APP_PHASE_FETCH_ARTICLE:
        return "FETCH_ARTICLE";
    case APP_PHASE_READY:
        return "READY";
    case APP_PHASE_ERROR:
        return "ERROR";
    }
    return "UNKNOWN";
}

static void begin_load(const char *loading_text, enum app_phase_t next_phase)
{
    printf("[app] begin_load text='%s' next=%s\n",
        loading_text ? loading_text : "(null)", phase_name(next_phase));
    ui_set_loading_text(loading_text);
    ui_show_splash();
    s_phase = APP_PHASE_SPLASH;
    s_phase_after_splash = next_phase;
    s_selection_ready = 0u;
}

static void begin_latest_load(const char *loading_text)
{
    s_pending_article_info = NULL;
    s_pending_article_title[0] = '\0';
    begin_load(loading_text, APP_PHASE_FETCH_LATEST);
}

static void begin_article_load(const char *title, const struct news_article_info *info)
{
    printf("[app] begin_article_load id=%lu title='%s'\n",
        info ? (unsigned long)info->id : 0ul,
        title ? title : "(null)");
    s_pending_article_info = info;
    strncpy(s_pending_article_title, title ? title : "", sizeof(s_pending_article_title) - 1u);
    s_pending_article_title[sizeof(s_pending_article_title) - 1u] = '\0';
    begin_load("Loading...", APP_PHASE_FETCH_ARTICLE);
}

static void show_article(const char *title, const struct news_article_info *info)
{
    printf("[app] show_article requested id=%lu title='%s'\n",
        info ? (unsigned long)info->id : 0ul,
        title ? title : "(null)");
    begin_article_load(title, info);
}

static void back_to_news(void)
{
    printf("[app] back_to_news\n");
    begin_latest_load("Loading...");
}

static void refresh_latest(void)
{
    printf("[app] refresh_latest\n");
    begin_latest_load("Refreshing...");
}

static void app_update(void)
{
    int r;

    switch (s_phase) {
    case APP_PHASE_SPLASH:
        printf("[app] phase SPLASH -> %s\n", phase_name(s_phase_after_splash));
        s_phase = s_phase_after_splash;
        break;
    case APP_PHASE_FETCH_LATEST:
        printf("[app] phase FETCH_LATEST\n");
        if (news_backend_fetch_latest() != 0) {
            printf("[app] news_backend_fetch_latest failed\n");
            ui_show_message("Load failed");
            s_phase = APP_PHASE_ERROR;
            break;
        }
        news_backend_reset_select(ui_news_select());
        s_selection_ready = 0u;
        s_phase = APP_PHASE_FILL_LATEST;
        printf("[app] latest fetched, moving to FILL_LATEST\n");
        break;
    case APP_PHASE_FILL_LATEST:
        printf("[app] phase FILL_LATEST selection_ready=%u options=%u\n",
            s_selection_ready,
            ui_news_select()->options_size);
        r = news_backend_fill_select(ui_news_select(), NEWS_SELECT_CAPACITY);
        printf("[app] fill result=%d options=%u\n", r, ui_news_select()->options_size);
        if (!s_selection_ready && ui_news_select()->options_size != 0u) {
            printf("[app] showing news list and activating first row\n");
            ui_show_news_list();
            ui_news_activate_first();
            s_selection_ready = 1u;
        }
        if (r <= 0) {
            s_phase = (r < 0) ? APP_PHASE_ERROR : APP_PHASE_READY;
            printf("[app] fill finished -> %s\n", phase_name(s_phase));
        }
        break;
    case APP_PHASE_FETCH_ARTICLE:
        printf("[app] phase FETCH_ARTICLE id=%lu title='%s'\n",
            s_pending_article_info ? (unsigned long)s_pending_article_info->id : 0ul,
            s_pending_article_title);
        if (!s_pending_article_info ||
            news_backend_fetch_article(s_pending_article_info->id, s_pending_article_title) != 0) {
            printf("[app] news_backend_fetch_article failed\n");
            ui_show_message("Article load failed");
            s_phase = APP_PHASE_ERROR;
            break;
        }
        printf("[app] article fetched title='%s'\n", s_pending_article_title);
        ui_show_article(news_backend_current_article());
        s_phase = APP_PHASE_READY;
        break;
    case APP_PHASE_READY:
        break;
    case APP_PHASE_ERROR:
        break;
    }
}

int app_init(void)
{
    printf("[app] init\n");
    if (news_backend_init() != 0) {
        printf("[app] news_backend_init failed\n");
        return -1;
    }

    ui_init(show_article, back_to_news, refresh_latest);
    s_pending_article_info = NULL;
    s_pending_article_title[0] = '\0';
    begin_latest_load("Loading...");
    printf("[app] init complete\n");
    return 0;
}

void app_iteration(void)
{
    ui_iteration();
    app_update();
#asm
    halt
#endasm
}
