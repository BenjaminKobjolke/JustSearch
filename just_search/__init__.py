"""JustSearch: one search plugin for fman. fman registers the commands, file
system, columns and listener it finds in this module's namespace."""
from .commands import (  # noqa: F401
    SearchFilesAndFoldersTokenBased, SearchFilesInSubFolders, SearchFilesInThisFolder,
    SearchFoldersTokenBased, SearchFoldersTokenBasedWithParent, SearchWithDialog,
    SearchWithLastSettings
)
from .pane_results import (  # noqa: F401
    RenameSearchResult, RunOnSearchResults, SearchName, SearchPath,
    SearchResultsFileSystem, SearchResultsListener
)
