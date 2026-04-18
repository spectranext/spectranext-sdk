#include <arch/zx/spectrum.h>
#include <stdio.h>
#include <string.h>

#include "ui.h"

#include "splash.h"
#include "scenes/app.inc.h"

#define NEWS_PREVIEW_BOX_X 0u
#define NEWS_PREVIEW_BOX_Y 17u
#define NEWS_PREVIEW_BOX_W 32u
#define NEWS_PREVIEW_BOX_H 6u

static ui_open_article_f s_open_article_cb;
static ui_back_f s_back_cb;
static ui_refresh_f s_refresh_cb;
static const struct gui_select_option_t *s_selected_option;

static void draw_box(uint8_t x, uint8_t y, uint8_t w, uint8_t h)
{
    uint8_t xx;
    uint8_t yy;
    const uint8_t right = x + w - 1u;
    const uint8_t bottom = y + h - 1u;

    zxgui_screen_put(x, y, GUI_ICON_TILE_BOX_LEFT_TOP);
    zxgui_screen_put(right, y, GUI_ICON_TILE_BOX_TOP_RIGHT);
    zxgui_screen_put(x, bottom, GUI_ICON_TILE_BOX_LEFT_BOTTOM);
    zxgui_screen_put(right, bottom, GUI_ICON_TILE_BOX_BOTTOM_RIGHT);

    for (xx = x + 1u; xx < right; ++xx) {
        zxgui_screen_put(xx, y, GUI_ICON_TILE_BOX_TOP);
        zxgui_screen_put(xx, bottom, GUI_ICON_TILE_BOX_BOTTOM);
    }

    for (yy = y + 1u; yy < bottom; ++yy) {
        zxgui_screen_put(x, yy, GUI_ICON_TILE_BOX_LEFT);
        zxgui_screen_put(right, yy, GUI_ICON_TILE_BOX_RIGHT);
    }
}

static void render_news_preview_box(void)
{
    draw_box(
        this_basics.x,
        this_basics.y,
        this_basics.w,
        this_basics.h);
    object_validate();
}

static struct gui_object_t news_preview_box = zxgui_base_init(
    NULL,
    NEWS_PREVIEW_BOX_X,
    NEWS_PREVIEW_BOX_Y,
    NEWS_PREVIEW_BOX_W,
    NEWS_PREVIEW_BOX_H,
    render_news_preview_box,
    NULL,
    GUI_FLAG_DIRTY);

static uint8_t *obtain_news_data(void)
{
    return news_backend_select_buffer();
}

static void on_news_selected(struct gui_select_option_t *selected)
{
    s_selected_option = selected;
    ui_set_news_preview(selected ? selected->value : "");
}

static void on_open_story_pressed(void)
{
    if (s_selected_option && s_open_article_cb) {
        s_open_article_cb(
            s_selected_option->value,
            news_backend_option_info(s_selected_option));
    }
}

static void on_refresh_pressed(void)
{
    if (s_refresh_cb) {
        s_refresh_cb();
    }
}

static void on_back_pressed(void)
{
    if (s_back_cb) {
        s_back_cb();
    }
}

static uint8_t on_news_scene_event(enum gui_event_type event_type, void *event)
{
    struct gui_event_key_pressed *ev;

    if (event_type != GUI_EVENT_KEY_PRESSED) {
        return 0;
    }

    ev = (struct gui_event_key_pressed *)event;
    if (ev->key == 'r' || ev->key == 'R') {
        on_refresh_pressed();
        return 1;
    }

    return 0;
}

static uint8_t on_article_scene_event(enum gui_event_type event_type, void *event)
{
    struct gui_event_key_pressed *ev;

    if (event_type != GUI_EVENT_KEY_PRESSED) {
        return 0;
    }

    ev = (struct gui_event_key_pressed *)event;
    if ((ev->key == GUI_KEY_CODE_ESCAPE || ev->key == GUI_KEY_CODE_BACKSPACE ||
         ev->key == 'b' || ev->key == 'B') && s_back_cb) {
        on_back_pressed();
        return 1;
    }

    return 0;
}

void ui_init(ui_open_article_f open_article_cb, ui_back_f back_cb, ui_refresh_f refresh_cb)
{
    printf("[ui] init\n");
    s_open_article_cb = open_article_cb;
    s_back_cb = back_cb;
    s_refresh_cb = refresh_cb;
    s_selected_option = NULL;
    strcpy(loading_text, "Loading...");
    news_preview_text[0] = '\0';

    screen_border = INK_BLACK;
    screen_color = INK_WHITE | PAPER_BLACK;

    splash_scene.on_event = NULL;
    news_scene.on_event = on_news_scene_event;
    article_scene.on_event = on_article_scene_event;

    if (zxgui_scene_get_last_object(&news_scene) != &news_preview_box) {
        zxgui_scene_add(&news_scene, &news_preview_box);
    }
}

void ui_show_splash(void)
{
    printf("[ui] show_splash\n");
    zxgui_clear();
    zxgui_scene_set(&splash_scene);
}

void ui_show_news_list(void)
{
    printf("[ui] show_news_list\n");
    zxgui_clear();
    zxgui_scene_set(&news_scene);
    zxgui_scene_set_focus(&news_scene, &news_select);
}

void ui_show_article(const struct news_article_details *article)
{
    printf("[ui] show_article title='%s' content='%s' url='%s'\n",
        article ? article->title : "(null)",
        article ? article->content : "(null)",
        article ? article->url : "(null)");
    article_title.base.flags |= GUI_FLAG_DIRTY;
    article_content.base.flags |= GUI_FLAG_DIRTY;
    article_url.base.flags |= GUI_FLAG_DIRTY;

    zxgui_clear();
    zxgui_scene_set(&article_scene);
}

void ui_show_message(const char *message)
{
    printf("[ui] show_message '%s'\n", message ? message : "(null)");
    strncpy(message_text, message ? message : "", sizeof(message_text) - 1u);
    message_text[sizeof(message_text) - 1u] = '\0';
    message_body.base.flags |= GUI_FLAG_DIRTY;

    zxgui_clear();
    zxgui_scene_set(&message_scene);
}

void ui_set_loading_text(const char *text)
{
    printf("[ui] set_loading_text '%s'\n", text ? text : "(null)");
    strncpy(loading_text, text, sizeof(loading_text) - 1u);
    loading_text[sizeof(loading_text) - 1u] = '\0';
    loading_label.base.flags |= GUI_FLAG_DIRTY;
}

void ui_set_news_preview(const char *text)
{
    printf("[ui] set_news_preview '%s'\n", text ? text : "(null)");
    strncpy(news_preview_text, text ? text : "", sizeof(news_preview_text) - 1u);
    news_preview_text[sizeof(news_preview_text) - 1u] = '\0';
    news_preview.base.flags |= GUI_FLAG_DIRTY;
    news_preview_box.flags |= GUI_FLAG_DIRTY;
}

void ui_iteration(void)
{
    zxgui_scene_iteration();
}

struct gui_select_t *ui_news_select(void)
{
    return &news_select;
}

void ui_news_activate_first(void)
{
    if (news_select.options_size == 0u) {
        printf("[ui] activate_first skipped, no options\n");
        s_selected_option = NULL;
        ui_set_news_preview("");
        return;
    }

    printf("[ui] activate_first options=%u\n", news_select.options_size);
    zxgui_scene_set_focus(&news_scene, &news_select);
    news_select.selection = 0u;
    news_select.last_selection = 0xFFu;
    zxgui_select_trigger_change_event(&news_select);
    news_select.base.flags |= GUI_FLAG_DIRTY | GUI_FLAG_DIRTY_INTERNAL;
}
