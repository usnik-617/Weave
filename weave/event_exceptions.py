from __future__ import annotations


class EventCommandError(Exception):
    pass


class EventNotFoundError(EventCommandError):
    pass


class EventVoteError(EventCommandError):
    pass
