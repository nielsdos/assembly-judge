from typing import Tuple, List

from dodona.translator import Translator
from exceptions.utils import DelayedExceptions


class HtmlValidationError(Exception):
    translator: Translator

    def __init__(self, translator: Translator): ...

    def __str__(self): ...

    def annotation(self) -> str: ...


class LocatableHtmlValidationError(HtmlValidationError):
    _tag_location: List[str]
    position: Tuple[int, int]

    def __init__(self, translator: Translator, tag_location: List[str], position: Tuple[int, int]): ...

    def location(self) -> str: ...

    def fpos(self) -> str: ...

    def annotation(self) -> str: ...

    def __str__(self): ...


class TagError(LocatableHtmlValidationError):
    tag: str

    def __init__(self, translator: Translator, tag_location: [str], position: (int, int), tag: str): ...

    def annotation(self) -> str: ...


class MissingOpeningTagError(TagError):
    def annotation(self) -> str: ...


class MissingClosingTagError(TagError):
    def annotation(self) -> str: ...


class InvalidTagError(TagError):
    def annotation(self) -> str: ...


class NoSelfClosingTagError(TagError):
    def annotation(self) -> str: ...


class UnexpectedTagError(TagError):
    def annotation(self) -> str: ...


class UnexpectedClosingTagError(TagError):
    def annotation(self) -> str: ...


class TagAttributeError(LocatableHtmlValidationError):
    tag: str
    attribute: str

    def __init__(self, translator: Translator, tag: str, tag_location: List[str], position: Tuple[int, int], attribute: str): ...

    def annotation(self) -> str: ...


class InvalidAttributeError(TagAttributeError):
    def annotation(self) -> str: ...


class MissingRequiredAttributesError(TagAttributeError):
    def annotation(self) -> str: ...


class DuplicateIdError(TagAttributeError):
    def annotation(self) -> str: ...


class AttributeValueError(LocatableHtmlValidationError):
    msg: str
    def __init__(self, translator: Translator, tag_location: [str], position: (int, int), message: str): ...

    def annotation(self) -> str: ...


class MissingRecommendedAttributesWarning(TagAttributeError):
    def annotation(self) -> str: ...


class Warnings(DelayedExceptions):
    translator: Translator
    exceptions: List[LocatableHtmlValidationError]

    def __init__(self, translator: Translator): ...

    def annotation(self) -> str: ...
