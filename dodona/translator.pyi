from enum import Enum
from typing import Dict

from dodona.dodona_command import ErrorType


class Translator:
    class Language(Enum):
        EN = ...
        NL = ...

    class Text(Enum):
        MISSING_EVALUATION_FILE = ...
        MISSING_CREATE_SUITE = ...
        MISSING_SUITES = ...
        TESTCASE_ABORTED = ...
        TESTCASE_NO_LONGER_EVALUATED = ...
        FAILED_TESTS = ...
        INVALID_LANGUAGE_TRANSLATION = ...
        INVALID_TESTSUITE_STUDENTS = ...
        EVALUATION_FAILED = ...
        # double char exceptions
        MISSING_OPENING_CHARACTER = ...
        MISSING_CLOSING_CHARACTER = ...
        # double char exceptions
        MISSING_OPENING_TAG = ...
        MISSING_CLOSING_TAG = ...
        INVALID_TAG = ...
        NO_SELF_CLOSING_TAG = ...
        UNEXPECTED_TAG = ...
        INVALID_ATTRIBUTE = ...
        MISSING_REQUIRED_ATTRIBUTE = ...
        DUPLICATE_ID = ...
        AT_LEAST_ONE_CHAR = ...
        NO_WHITESPACE = ...
        NO_ABS_PATHS = ...
        MISSING_RECOMMENDED_ATTRIBUTE = ...
        AMBIGUOUS_XPATH = auto()
        #comparer text
        EMPTY_SUBMISSION = ...
        TAGS_DIFFER = ...
        ATTRIBUTES_DIFFER = ...
        NOT_ALL_ATTRIBUTES_PRESENT = ...
        CONTENTS_DIFFER = ...
        AMOUNT_CHILDREN_DIFFER = ...
        STYLES_DIFFER = ...
        EXPECTED_COMMENT = ...
        COMMENT_CORRECT_TEXT = ...
        AT_LINE = ...
        SIMILARITY = ...
        # normal text
        ERRORS = ...
        WARNINGS = ...
        LOCATED_AT = ...
        LINE = ...
        POSITION = ...
        SUBMISSION = ...

    language: Language

    def __init__(self, language: Language): ...

    @classmethod
    def from_str(cls, language: str) -> "Translator": ...

    def human_error(self, error: ErrorType) -> str: ...

    def error_status(self, error: ErrorType, **kwargs) -> Dict[str, str]: ...

    def translate(self, message: Text, **kwargs) -> str: ...

    error_translations: Dict[Language, Dict[ErrorType, str]]
    text_translations: Dict[Language, Dict[Text, str]]