"""Basic checking library to create evaluation tests for exercises"""
import re

from bs4 import BeautifulSoup
from bs4.element import Tag
from copy import deepcopy
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional, Callable, Union

from dodona.dodona_command import Context, TestCase, Message, MessageFormat
from dodona.translator import Translator
from validators.html_validator import HtmlValidator
from exceptions.htmlExceptions import EvaluationAborted, Warnings, HtmlValidationError


@dataclass
class Check:
    """Class that represents a single check

    Attributes:
        message     Message to display to the user in the checklist.
        callback    The function to run in order to perform this test.
        on_success  A list of checks that will only be performed in case this
                    check succeeds. An example of how this could be useful is to
                    first test if an element exists and THEN perform extra checks
                    on its attributes and/or children. This avoids unnecessary spam
                    to the user, because an element that doesn't exist never has
                    the correct specifications.
        hidden      Indicate that the message from this check should NOT be shown
                    in the final checklist. Again avoids unnecessary spam and can
                    help hide checks that would reveal the answer to the student.
    """
    callback: Callable[[BeautifulSoup], bool]
    on_success: List["Check"] = field(default_factory=list)
    abort_on_fail: bool = False

    def _find_deepest_nested(self) -> "Check":
        """Find the deepest Check nested with on_success chains"""
        current_deepest = self.on_success[-1]

        # Keep going until the current one no longer contains anything
        while current_deepest.on_success:
            current_deepest = current_deepest.on_success[-1]

        return current_deepest

    def or_abort(self) -> "Check":
        """Prevent the next tests from running if this one fails
        Can be used when a test is necessary for the rest to continue, for example
        the HTML-validation step.
        """
        self.abort_on_fail = True
        return self

    def is_crucial(self) -> "Check":
        """Alias to or_abort()"""
        return self.or_abort()

    def then(self, *args: "Check") -> "Check":
        """Register a list of checks to perform in case this check succeeds
        When this check already has checks registered, try to find the deepest check
        and append it to that check. The reasoning is that x.then(y).then(z) suggests y should
        complete for z to start. This makes the overall use more fluent and avoids
        a big mess of brackets when it's not necessary at all.

        Returns a reference to the last entry to allow a fluent interface.
        """
        if not self.on_success:
            self.on_success = list(args)
        else:
            # Find the deepest child check and add to that one
            deepest: "Check" = self._find_deepest_nested()
            deepest.on_success = list(args)

        return args[-1]


@dataclass
class Element:
    """Class for an HTML element used in testing

    Attributes:
        tag         The HTML tag of this element.
        id          An optional id to specify when searching for the element,
                    if not specified then the first result found will be used.
        _element    The inner HTML element that was matched in the document,
                    can be None if nothing was found.
    """
    tag: str
    id: Optional[str] = None
    _element: Optional[Tag] = None

    def __str__(self):
        if self.id is not None:
            return f"<{self.tag} id={self.id}>"

        return f"<{self.tag}>"

    def get_child(self, tag: str, index: int = 0, direct: bool = True, **kwargs) -> "Element":
        """Find the child element with the given tag

        :param tag:     the tag to search for
        :param index:   in case multiple children are found, specify the index to fetch
                        if not enough children were found, still return the first
        :param direct:  indicate that only direct children should be considered
        """
        # This element was not found, so the children don't exist either
        if self._element is None:
            return Element(tag, kwargs.get("id", None), None)

        # No index specified, first child requested
        if index == 0:
            child = self._element.find(tag, recursive=not direct, **kwargs)
        else:
            all_children = self._element.find_all(tag, recursive=not direct, **kwargs)

            # No children found
            if len(all_children) == 0:
                child = None
            else:
                # Not enough children found (index out of range)
                if index >= len(all_children):
                    index = 0

                child = all_children[index]

        if child is None:
            return EmptyElement()

        return Element(tag, child.get("id", None), child)

    def get_children(self, tag: str = "", direct: bool = True, **kwargs) -> "ElementContainer":
        """Get all children of this element that match the requested input"""
        # This element doesn't exist so it has no children
        if self._element is None:
            return ElementContainer([])

        # If a tag was specified, only search for those
        # Otherwise, use all children instead
        if tag:
            matches = self._element.find_all(tag, recursive=not direct, **kwargs)
        else:
            matches = self._element.children if direct else self._element.descendants

            # Filter out string content
            matches = list(filter(lambda x: isinstance(x, Tag), matches))

        elements = list(map(lambda x: Element(x.name, x.get("id", None), x), matches))
        return ElementContainer(elements)

    def exists(self) -> Check:
        """Check that this element was found"""

        def _inner(_: BeautifulSoup) -> bool:
            return self._element is not None

        return Check(_inner)

    def has_child(self, tag: str, direct: bool = True, **kwargs) -> Check:
        """Check that this element has a child with the given tag

        :param tag:     the tag to search for
        :param direct:  indicate that only direct children should be considered,
                        no elements of children
        """

        def _inner(_: BeautifulSoup) -> bool:
            if self._element is None:
                return False

            return self._element.find(tag, recursive=not direct, **kwargs) is not None

        return Check(_inner)

    def has_content(self, text: Optional[str] = None) -> Check:
        """Check if this element has given text as content.
        In case no text is passed, any non-empty string will make the test pass

        Example:
        >>> suite = TestSuite("<p>This is some text</p>")
        >>> element = suite.element("p")
        >>> element.has_content()
        True
        >>> element.has_content("This is some text")
        True
        >>> element.has_content("Something else")
        False
        """

        def _inner(_: BeautifulSoup) -> bool:
            # Element doesn't exist
            if self._element is None:
                return False

            if text is not None:
                return self._element.text == text

            return len(self._element.text) > 0

        return Check(_inner)

    def count_children(self, tag: str, amount: int, direct: bool = True, **kwargs) -> Check:
        """Check that this element has exactly [amount] children matching the requirements"""

        def _inner(_: BeautifulSoup) -> bool:
            if self._element is None:
                return False

            return len(self._element.find_all(tag, recursive=not direct, **kwargs)) == amount

        return Check(_inner)

    def _has_tag(self, tag: str) -> bool:
        """Internal function that checks if this element has the required tag"""
        return self._element is not None and self._element.name == tag

    def has_tag(self, tag: str) -> Check:
        """Check that this element has the required tag"""

        def _inner(_: BeautifulSoup) -> bool:
            return self._has_tag(tag)

        return Check(_inner)

    def _get_attribute(self, attr: str) -> Optional[str]:
        """Internal function that gets an attribute"""
        if self._element is None:
            return None

        attribute = self._element.get(attr)

        return attribute

    def has_attribute(self, attr: str, value: Optional[str] = None) -> Check:
        """Check that this element has the required attribute, optionally with a value
        :param attr:    The name of the attribute to check.
        :param value:   The value to check. If no value is passed, this will not be checked.
        """
        def _inner(_: BeautifulSoup) -> bool:
            attribute = self._get_attribute(attr)

            # Attribute wasn't found
            if attribute is None:
                return False

            # No value specified
            if value is None:
                return True

            return attribute == value

        return Check(_inner)

    def attribute_contains(self, attr: str, substr: str) -> Check:
        """Check that the value of this attribute contains a substring"""
        def _inner(_: BeautifulSoup) -> bool:
            attribute = self._get_attribute(attr)

            # Attribute wasn't found
            if attribute is None:
                return False

            return substr in attribute

        return Check(_inner)

    def attribute_matches(self, attr: str, regex: re.Pattern):
        """Check that the value of an attribute matches a regex pattern"""
        def _inner(_: BeautifulSoup) -> bool:
            attribute = self._get_attribute(attr)

            # Attribute wasn't found
            if attribute is None:
                return False

            return re.match(regex, attribute) is not None

        return Check(_inner)

    def has_table_header(self, header: List[str]) -> Check:
        """If this element is a table, check that the header content matches up"""
        def _inner(_: BeautifulSoup) -> bool:
            # This element is either None or not a table
            if not self._has_tag("table"):
                return False

            # List of all headers in this table
            ths = self._element.find_all("th")

            # Not the same amount of headers
            if len(ths) != len(header):
                return False

            # Check if all headers have the same content in the same order
            for i in range(len(header)):
                if header[i] != ths[i].text:
                    return False

            return True

        return Check(_inner)

    def has_table_content(self, rows: List[List[str]], has_header: bool = True) -> Check:
        """Check that a table's rows have the requested content
        :param rows:        The data of all the rows to check
        :param has_header:  Boolean that indicates that this table has a header,
                            so the first row will be ignored (!)
        """
        def _inner(_: BeautifulSoup) -> bool:
            # This element is either None or not a table
            if not self._has_tag("table"):
                return False

            trs = self._element.find_all("tr")

            # No rows found
            if not trs:
                return False

            # Cut header out
            if has_header:
                trs = trs[1:]

                # Table only had a header, no actual content
                if not trs:
                    return False

            # Compare tds (actual data)
            for i in range(len(rows)):
                data = trs[i].find_all("td")

                # Row doesn't have the same amount of tds
                if len(data) != len(rows[i]):
                    return False

                # Compare content
                for j in range(len(rows[i])):
                    # Content doesn't match
                    if data[j].text != rows[i][j]:
                        return False

            return True

        return Check(_inner)

    def table_row_has_content(self, row: List[str]) -> Check:
        """Check the content of one row instead of the whole table"""
        def _inner(_: BeautifulSoup) -> bool:
            # Check that this element exists and is a <tr>
            if not self._has_tag("tr"):
                return False

            tds = self._element.find_all("td")

            # Amount of items doesn't match up
            if len(tds) != len(row):
                return False

            for i in range(len(row)):
                # Text doesn't match
                if row[i] != tds[i].text:
                    return False

            return True

        return Check(_inner)


@dataclass
class EmptyElement(Element):
    """Class that represents an element that could not be found"""
    def __init__(self):
        super().__init__("", None, None)


@dataclass
class ElementContainer:
    """Class used for collections of elements fetched from the HTML
    This class was made to avoid potential IndexErrors in the evaluation file
    when using indexing.

    The example below assumes that there are two <div>s in the solution in order
    to set up the checklist, but the student's current file may not have these.
    This would cause IndexErrors when parsing the file.

    By letting get_children() return this container class, we can just return an
    empty Element() object when the list doesn't have enough elements, and then
    other checks will just fail instead of crashing.
    Example:
    >>> suite = TestSuite("<body>"
    ...                     "<div id='div1'>"
    ...                         "..."
    ...                     "</div>"
    ...                     "<div id='div2'>"
    ...                         "..."
    ...                     "</div>"
    ...                   "</body>")
    >>> all_divs = suite.element("body").get_children("div")
    >>> all_divs[1].has_child("...")  # IndexError if student doesn't have this!

    Attributes:
        elements       the elements to add into this container
    """
    elements: List[Element]
    _size: int = field(init=False)

    def __post_init__(self):
        # Avoid calling len() all the time
        self._size = len(self.elements)

    def __getitem__(self, item) -> Element:
        if not isinstance(item, int):
            raise TypeError(f"Key {item} was of type {item}, not int.")

        # Out of range
        if item >= self._size:
            return EmptyElement()

        return self.elements[item]

    def __len__(self):
        return self._size

    def get(self, index: int) -> Element:
        """Get an item at a given index, same as []-operator"""
        return self[index]

    def at_most(self, amount: int) -> Check:
        """Check that a container has at most [amount] elements"""

        def _inner(_: BeautifulSoup):
            return self._size <= amount

        return Check(_inner)

    def at_least(self, amount: int) -> Check:
        """Check that a container has at least [amount] elements"""

        def _inner(_: BeautifulSoup):
            return self._size >= amount

        return Check(_inner)

    def exactly(self, amount: int) -> Check:
        """Check that a container has exactly [amount] elements"""

        def _inner(_: BeautifulSoup) -> bool:
            return self._size == amount

        return Check(_inner)


def _flatten_queue(queue: List) -> List[Check]:
    """Flatten the queue to allow nested lists to be put it"""
    flattened: List[Check] = []

    while queue:
        el = queue.pop(0)

        # This entry is a list too, unpack it
        # & add to front of the queue
        if isinstance(el, list):
            # Iterate in reverse to keep the order of checks!
            for nested_el in reversed(el):
                queue.insert(0, nested_el)
        else:
            flattened.append(el)

    return flattened


@dataclass
class ChecklistItem:
    """An item to add to the checklist

    Attributes:
        message     The message displayed on the Dodona checklist for this item
        checklist   List of Checks to run, all of which should pass for this item
                    to be marked as passed/successful on the final list
    """
    message: str
    # People can pass nested lists into this, so the type is NOT List[Check] yet
    checks: Union[List, Check] = field(default_factory=list)
    _checks: List[Check] = field(init=False)

    def __post_init__(self):
        self._checks = []

        # Only one check was passed
        if isinstance(self.checks, Check):
            self._checks.append(self.checks)
            return

        # Flatten the list of checks and store in internal list
        for item in self.checks:
            if isinstance(item, Check):
                self._checks.append(item)
            elif isinstance(item, list):
                # Group the list into one main check and add that one
                self._checks.append(all_of(item))

    def evaluate(self, bs: BeautifulSoup) -> bool:
        """Evaluate all checks inside of this item"""
        for check in self._checks:
            if not check.callback(bs):
                # Abort testing if necessary
                if check.abort_on_fail:
                    raise EvaluationAborted()

                return False

        return True


@dataclass
class TestSuite:
    """Main test suite class

    Attributes:
        content     The HTML of the document to perform the tests on
        checklist   A list of all checks to perform on this document
    """
    name: str
    content: str
    checklist: List[ChecklistItem] = field(default_factory=list)
    _bs: BeautifulSoup = field(init=False)
    _root: Tag = field(init=False)

    _validator: HtmlValidator = HtmlValidator(check_recommended=True)

    def __post_init__(self):
        self._bs = BeautifulSoup(self.content, "html.parser")

        # TODO don't require this anymore
        self._root = self._bs.html

    def validate_html(self, allow_warnings=True) -> Check:
        """Check that the HTML is valid
        This is done in here so that all errors and warnings can be sent to
        Dodona afterwards by reading them out of here

        The CODE format is used because it preserves spaces & newlines
        """

        def _inner(_: BeautifulSoup) -> bool:
            try:
                self._validator.validate_content(self.content)
            except Warnings as war:
                with Message(description=str(war), format=MessageFormat.CODE):
                    return allow_warnings
            except HtmlValidationError as err:
                with Message(description=str(err), format=MessageFormat.CODE):
                    return False

            # If no validation errors were raised, the HTML is valid
            return True

        return Check(_inner)

    def element(self, tag: str, from_root=True, **kwargs) -> Element:
        """Create a reference to an HTML element
        :param tag:         the name of the HTML tag to search for
        :param from_root:   find the element as a child of the root node instead of anywhere
                            in the document
        """
        start: Union[BeautifulSoup, Tag] = self._root if from_root else self._bs

        element = start.find(tag, **kwargs)
        return Element(tag, kwargs.get("id", None), element)

    def evaluate(self, translator: Translator) -> int:
        """Run the test suite, and print the Dodona output
        :returns:   the amount of failed tests
        :rtype:     int
        """
        aborted = -1
        failed_tests = 0

        # Run all items on the checklist & mark them as successful if they pass
        for i, item in enumerate(self.checklist):
            with Context(), TestCase(item.message) as test_case:
                # Make it False by default so crashing doesn't make it default to True
                test_case.accepted = False

                # Evaluation was aborted, print a message and skip this test
                if aborted >= 0:
                    with Message(description=translator.translate(translator.Text.TESTCASE_NO_LONGER_EVALUATED),
                                 format=MessageFormat.TEXT):
                        failed_tests += 1
                        continue

                # Can't set items on tuples so overwrite it
                try:
                    test_case.accepted = item.evaluate(self._bs)
                except Warnings as war:
                    # Warnings don't cause the test to fail, but must still be printed
                    with Message(description=str(war), format=MessageFormat.CODE):  # code preserves spaces & newlines
                        test_case.accepted = True
                except HtmlValidationError as err:
                    with Message(description=str(err), format=MessageFormat.CODE):  # code preserves spaces & newlines
                        pass
                except EvaluationAborted:
                    # Crucial test failed, stop evaluation and let the next tests
                    # all be marked as wrong
                    aborted = i

                    with Message(description=translator.translate(translator.Text.TESTCASE_ABORTED),
                                 format=MessageFormat.TEXT):
                        pass

                # If the test wasn't marked as True above, increase the counter for failed tests
                if not test_case.accepted:
                    failed_tests += 1

        return failed_tests


def all_of(args: List[Check]) -> Check:
    """Perform an AND-statement on a list of Checks
    Creates a new Check that requires every single one of the checks to pass,
    otherwise returns False.
    """
    # Flatten list of checks
    flattened = _flatten_queue(deepcopy(args))
    queue: Deque[Check] = deque(flattened)

    def _inner(bs: BeautifulSoup) -> bool:
        while queue:
            check = queue.popleft()

            # One check failed, return False
            if not check.callback(bs):
                return False

            # Try the other checks
            for sub in reversed(check.on_success):
                queue.appendleft(sub)

        return True

    return Check(_inner)


def any_of(args: List[Check]) -> Check:
    """Perform an OR-statement on a list of Checks
    Returns True if at least one of the tests succeeds, and stops
    evaluating the rest at that point.
    """
    # Flatten list of checks
    flattened = _flatten_queue(deepcopy(args))
    queue: Deque[Check] = deque(flattened)

    def _inner(bs: BeautifulSoup) -> bool:
        while queue:
            check = queue.popleft()

            # One check failed, return False
            if check.callback(bs):
                return True

            # Try the other checks
            for sub in reversed(check.on_success):
                queue.appendleft(sub)

        return False

    return Check(_inner)


def fail_if(check: Check) -> Check:
    """Fail if the inner Check returns True
    Equivalent to the not-operator.
    """
    def _inner(bs: BeautifulSoup):
        return not check.callback(bs)

    return Check(_inner)
