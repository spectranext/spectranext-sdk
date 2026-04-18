#ifndef UI_H
#define UI_H

#include "news_backend.h"
#include "zxgui.h"

typedef void (*ui_open_article_f)(const char *title, const struct news_article_info *info);
typedef void (*ui_back_f)(void);
typedef void (*ui_refresh_f)(void);

void ui_init(ui_open_article_f open_article_cb, ui_back_f back_cb, ui_refresh_f refresh_cb);
void ui_show_splash(void);
void ui_show_news_list(void);
void ui_show_article(const struct news_article_details *article);
void ui_show_message(const char *message);
void ui_set_loading_text(const char *text);
void ui_iteration(void);
void ui_set_news_preview(const char *text);

struct gui_select_t *ui_news_select(void);
void ui_news_activate_first(void);

#endif
