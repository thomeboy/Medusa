# coding=utf-8

"""Custom exceptions used or raised by indexer_api."""


class IndexerException(Exception):
    """Any exception generated by indexers api."""


class IndexerError(IndexerException):
    """An error with the indexers api (Cannot connect, for example)."""


class IndexerUserAbort(IndexerException):
    """User aborted the interactive selection (via the q command, ^c etc)."""


class IndexerShowNotFound(IndexerException):
    """Show cannot be found in the indexer (non-existant show)."""


class IndexerShowNotFoundInLanguage(IndexerException):
    """Show cannot be found in the indexer with this language."""

    def __init__(self, message, language):
        """Initialize exception with language."""
        super(IndexerShowNotFoundInLanguage, self).__init__(message)
        self.language = language


class IndexerShowIncomplete(IndexerException):
    """Show found but incomplete in the indexer (incomplete show)."""


class IndexerSeasonNotFound(IndexerException):
    """Season cannot be found in the indexer."""


class IndexerEpisodeNotFound(IndexerException):
    """Episode cannot be found in the indexer."""


class IndexerAttributeNotFound(IndexerException):
    """Raised if an episode does not have the requested attribute (such as a episode name)."""


class IndexerSeasonUpdatesNotSupported(IndexerException):
    """Raised if an episode does not have the requested attribute (such as a episode name)."""


class IndexerUnavailable(IndexerError):
    """Indexer API is unavailable, for example when giving back a 5xx response."""


class IndexerShowAllreadyInLibrary(IndexerException):
    """The show is already in the library. Same show for multiple indexers, is not supported."""


class IndexerAuthFailed(IndexerException):
    """Indexer authentication exception."""