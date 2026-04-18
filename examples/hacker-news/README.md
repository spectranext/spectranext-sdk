# Hacker News example

This example is a small Spectranext GUI application that fetches stories from the [HNPWA API](https://github.com/tastejs/hacker-news-pwa), displays a selectable list of stories, and loads a single story on demand.

The current implementation uses:

- `zxgui` for the UI
- `libspectranet` and HTTPS mounts for network access
- `spectranext_enginecall()` with the `json` engine to extract only the fields needed by the Z80
- RAM XFS files as the exchange format between the engine and the application

## What it does

At startup the app:

1. Detects that it is running on Spectranext.
2. Mounts `https://api.hnpwa.com/v0` on mount `3`.
3. Shows a splash screen while loading.
4. Fetches page 1 of the HNPWA `show` feed from `show/1.json`.
5. Extracts only story `id` and `title` into `news.bin` on RAM mount `0`.
6. Fills the story list and shows the news scene.

When a story is opened, the app fetches `item/<id>.json`, extracts `content` and `url` into `article.bin`, and displays the result in the article screen.

## UI and controls

The app has four screens:

- Splash screen with a loading message
- News list screen with a preview box
- Article screen showing title, content, and URL
- Message screen for fatal errors

Controls:

- `Enter`: open the selected story
- `R`: refresh the story list
- `B`: go back from the article screen
- `Esc`: go back from the article screen
- `Backspace`: go back from the article screen

The first story is selected automatically after the list is loaded.

## Data flow

### Latest stories

The latest list is loaded with:

```c
spectranext_enginecall(
    "3:show/1.json",
    "news.bin",
    "json '$[*][\"id\",\"title\"]'")
```

The resulting `news.bin` file is read back from RAM mount `0` and used to populate the select widget. The current implementation stores up to `16` story entries in the UI buffer.

### Article details

The selected story is loaded with:

```c
spectranext_enginecall(
    "3:item/<id>.json",
    "article.bin",
    "json '$.content' '$.url'")
```

The app then reads `article.bin` from RAM mount `0` and fills:

- article content
- article URL

If the API returns an empty `content` field, the app shows `(no content)`.

## Build

This example is built through the Spectranext SDK CMake toolchain.

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

The build also generates UI assets from source files in this example:

- scene definitions from [`scenes/app.yaml`](/Users/desert/Documents/Work/spectranext-sdk/examples/hacker-news/scenes/app.yaml)
- tiles from `img/tiles.png`
- splash image data from `img/splash.png`

`Python3` is required at configure time because the asset generation tools are run from CMake.

## Requirements

- Spectranext hardware or firmware support detectable by `spectranext_detect()`
- HTTPS mount support
- `spectranext_enginecall()` support
- `json` engine support on the RP2350 side

## Notes

- This example currently uses the HNPWA `show` feed, not the Hacker News `news` feed.
- The article view displays the extracted `content` and `url` fields directly. It does not perform HTML rendering or additional content cleanup.
- On load failure, the app switches to a simple message screen.
