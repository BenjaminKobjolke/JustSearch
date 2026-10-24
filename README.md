# JustSearch

One search plugin for [fman](https://fman.io). Find files and folders below the
current folder by words, wildcards, regular expression, fuzzy match or file content.
Results show in a search window, or flat in the pane.

It replaces two plugins:
[fman-search-window-2022](https://github.com/BenjaminKobjolke/fman-search-window-2022)
and [FuzzySearchFilesInCurrentFolder](https://github.com/BenjaminKobjolke/FuzzySearchFilesInCurrentFolder).
Uninstall them first: all three register the `search://` scheme.

## Installation

Copy this folder to fman's user plugins folder and restart fman:

- Windows: `%APPDATA%\fman\Plugins\User\JustSearch`
- macOS: `~/Library/Application Support/fman/Plugins/User/JustSearch`
- Linux: `~/.config/fman/Plugins/User/JustSearch`

No dependencies beyond fman.

## Search window

`Ctrl+F7` (`Cmd+F7` on macOS), or `Search With Dialog` in the command palette.

| Field | Meaning |
|---|---|
| Name | What to look for. Empty matches everything. |
| Match | `Words in name`: every word appears in the name, any order, case ignored. `Words in path`: the words appear in this order in the path below the folder (`fraenk 2026` finds `fraenk/.../2026`). `Wildcards`: `*.pdf`, `Test*`. `Regular expression`: searched in the name, case ignored. `Fuzzy`: the letters appear in order in the path. |
| Find | Files and folders, files only, or folders only. Folders only never lists files, so it is fast on big trees. |
| Depth | `all`, `0` for this folder only, or how many levels of subfolders. |
| Folder | Where to search. Opens on the pane's folder. |
| Text in files | Only files that contain this text, read with the chosen encoding. Case-sensitive unless `Ignore case` is checked (off by default). |

Results appear while the search runs; `Stop` ends it. `Enter` or a double click on
a result opens its folder in the pane with the cursor on it. `Show in pane` lists all
results flat in the pane and closes the window.

Keys: `F1` name, `F2` folder, `F3` results, `Esc` closes.

## Commands without the window

Find these in the command palette. The plugin binds no keys for them; add your own
in fman's `Key Bindings.json`.

| Command | What it does |
|---|---|
| `Search Files And Folders Token Based` | Prompt, words in name, files and folders, results in the pane. |
| `Search Folders Token Based` | Same, folders only. |
| `Search Folders Token Based With Parent` | Folders only, words in order in the path. |
| `Search With Last Settings` | Prompt, then search with the search window's last settings. |
| `Search Files In This Folder` | Fuzzy quicksearch over the current folder; `Enter` puts the cursor on the item. |
| `Search Files In Sub Folders` | Fuzzy quicksearch over all subfolders; `Enter` opens the item's folder. |

The prompts are prefilled with the last query, fully selected: `Enter` repeats the
search, typing replaces it. Running a search while the pane shows results searches the
folder those results came from.

## Results in the pane

The pane shows `search://<folder>` with the columns Name, Path, Size and Modified.
`Enter` opens a folder, or opens a file's folder with the cursor on the file. Copy and
the other file operations work on the real files.

## Settings

Stored in `Just Search.json` in fman's settings folder
(`%APPDATA%\fman\Plugins\User\Settings` on Windows): the last search, the name and
text histories (10 entries each), and the folders that are never entered:

```json
{
    "excluded_folders": [".obsidian", ".git", ".trash", ".stfolder", ".stversions", "node_modules"]
}
```

## Development

`test_just_search.py` checks the matching and folder walk without fman:

```
python test_just_search.py
```
