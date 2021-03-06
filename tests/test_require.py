"""Tests for validation and comparison functions."""
import re
import textwrap
from . import _unittest as unittest
from datatest.utils.misc import _is_consumable

from datatest.errors import Extra
from datatest.errors import Missing
from datatest.errors import Invalid
from datatest.errors import Deviation
from datatest.errors import NOTFOUND

from datatest.require import _require_sequence
from datatest.require import _require_set
from datatest.require import _require_callable
from datatest.require import _require_regex
from datatest.require import _require_equality
from datatest.require import _require_single_equality
from datatest.require import _get_msg_and_func
from datatest.require import _apply_mapping_requirement
from datatest.require import _get_difference_info


class TestRequireSequence(unittest.TestCase):
    def test_no_difference(self):
        first = ['aaa', 'bbb', 'ccc']
        second = ['aaa', 'bbb', 'ccc']
        error = _require_sequence(first, second)
        self.assertIsNone(error)  # No difference, returns None.

    def test_extra(self):
        data = ['aaa', 'bbb', 'ccc', 'ddd', 'eee']
        requirement = ['aaa', 'ccc', 'eee']
        error = _require_sequence(data, requirement)
        self.assertEqual(error, {(1, 1): Extra('bbb'), (3, 2): Extra('ddd')})

    def test_extra_with_empty_requirement(self):
        data = ['aaa', 'bbb']
        requirement = []
        error = _require_sequence(data, requirement)
        self.assertEqual(error, {(0, 0): Extra('aaa'), (1, 0): Extra('bbb')})

    def test_missing(self):
        data = ['bbb', 'ddd']
        requirement = ['aaa', 'bbb', 'ccc', 'ddd', 'eee']
        error = _require_sequence(data, requirement)
        expected = {
            (0, 0): Missing('aaa'),
            (1, 2): Missing('ccc'),
            (2, 4): Missing('eee'),
        }
        self.assertEqual(error, expected)

    def test_missing_with_empty_data(self):
        data = []
        requirement = ['aaa', 'bbb']
        error = _require_sequence(data, requirement)
        self.assertEqual(error, {(0, 0): Missing('aaa'), (0, 1): Missing('bbb')})

    def test_invalid(self):
        data = ['aaa', 'bbb', '---', 'ddd', 'eee']
        requirement = ['aaa', 'bbb', 'ccc', 'ddd', 'eee']
        actual = _require_sequence(data, requirement)
        expected = {
            (2, 2): Invalid('---', 'ccc'),
        }
        self.assertEqual(actual, expected)

    def test_mixed_differences(self):
        data = ['aaa', '---', 'ddd', 'eee', 'ggg']
        requirement = ['aaa', 'bbb', 'ccc', 'ddd', 'fff']
        actual = _require_sequence(data, requirement)
        expected = {
            (1, 1): Invalid('---', 'bbb'),
            (2, 2): Missing('ccc'),
            (3, 4): Invalid('eee', 'fff'),
            (4, 5): Extra('ggg'),
        }
        self.assertEqual(actual, expected)

    def test_unhashable(self):
        """Uses "deep hashing" to attempt to sort unhashable types."""
        first = [{'a': 1}, {'b': 2}, {'c': 3}]
        second = [{'a': 1}, {'b': 2}, {'c': 3}]
        error = _require_sequence(first, second)
        self.assertIsNone(error)  # No difference, returns None.

        data = [{'a': 1}, {'-': 0}, {'d': 4}, {'e': 5}, {'g': 7}]
        requirement = [{'a': 1}, {'b': 2}, {'c': 3}, {'d': 4}, {'f': 6}]
        actual = _require_sequence(data, requirement)
        expected = {
            (1, 1): Invalid({'-': 0}, {'b': 2}),
            (2, 2): Missing({'c': 3}),
            (3, 4): Invalid({'e': 5}, {'f': 6}),
            (4, 5): Extra({'g': 7}),
        }
        self.assertEqual(actual, expected)


class TestRequireSet(unittest.TestCase):
    def setUp(self):
        self.requirement = set(['a', 'b', 'c'])

    def test_no_difference(self):
        data = iter(['a', 'b', 'c'])
        result = _require_set(data, self.requirement)
        self.assertIsNone(result)  # No difference, returns None.

    def test_missing(self):
        data = iter(['a', 'b'])
        result = _require_set(data, self.requirement)
        self.assertEqual(list(result), [Missing('c')])

    def test_extra(self):
        data = iter(['a', 'b', 'c', 'x'])
        result = _require_set(data, self.requirement)
        self.assertEqual(list(result), [Extra('x')])

    def test_duplicate_extras(self):
        """Should return only one error for each distinct extra value."""
        data = iter(['a', 'b', 'c', 'x', 'x', 'x'])  # <- Multiple x's.
        result = _require_set(data, self.requirement)
        self.assertEqual(list(result), [Extra('x')])

    def test_missing_and_extra(self):
        data = iter(['a', 'c', 'x'])
        result = _require_set(data, self.requirement)

        result = list(result)
        self.assertEqual(len(result), 2)
        self.assertIn(Missing('b'), result)
        self.assertIn(Extra('x'), result)

    def test_string_or_noniterable(self):
        data = 'a'
        result = _require_set(data, self.requirement)

        result = list(result)
        self.assertEqual(len(result), 2)
        self.assertIn(Missing('b'), result)
        self.assertIn(Missing('c'), result)

    def test_notfound(self):
        result = _require_set(NOTFOUND, set(['a']))
        self.assertEqual(list(result), [Missing('a')])


class TestRequireCallable(unittest.TestCase):
    def setUp(self):
        self.isdigit = lambda x: x.isdigit()

    def test_all_true(self):
        data = ['10', '20', '30']
        result = _require_callable(data, self.isdigit)
        self.assertIsNone(result)

    def test_some_false(self):
        """Elements that evaluate to False are returned as Invalid() errors."""
        data = ['10', '20', 'XX']
        result = _require_callable(data, self.isdigit)
        self.assertEqual(list(result), [Invalid('XX')])

    def test_duplicate_false(self):
        """Should return an error for every false result (incl. duplicates)."""
        data = ['10', '20', 'XX', 'XX', 'XX']  # <- Multiple XX's.
        result = _require_callable(data, self.isdigit)
        self.assertEqual(list(result), [Invalid('XX'), Invalid('XX'), Invalid('XX')])

    def test_raised_error(self):
        """When an Exception is raised, it counts as False."""
        data = ['10', '20', 30]  # <- Fails on 30 (int has no 'isdigit' method).
        result = _require_callable(data, self.isdigit)
        self.assertEqual(list(result), [Invalid(30)])

    def test_returned_error(self):
        """When a difference is returned, it is used in place of Invalid."""
        def func(x):
            if x == 'c':
                return Invalid("Letter 'c' is no good!")
            return True

        data = ['a', 'b', 'c']
        result = _require_callable(data, func)
        self.assertEqual(list(result), [Invalid("Letter 'c' is no good!")])

    def test_bad_return_type(self):
        """If callable returns an unexpected type, raise a TypeError."""
        def func(x):
            return Exception('my error')  # <- Not True, False or difference!

        with self.assertRaises(TypeError):
            result = _require_callable(['a', 'b', 'c'], func)
            list(result)  # Evaluate generator.

    def test_notfound(self):
        def func(x):
            return False
        result = _require_callable(NOTFOUND, func)
        self.assertEqual(result, Invalid(None))


class TestRequireRegex(unittest.TestCase):
    def setUp(self):
        self.regex = re.compile('[a-z][0-9]+')

    def test_all_true(self):
        data = iter(['a1', 'b2', 'c3'])
        result = _require_regex(data, self.regex)
        self.assertIsNone(result)

    def test_some_false(self):
        data = iter(['a1', 'b2', 'XX'])
        result = _require_regex(data, self.regex)
        self.assertEqual(list(result), [Invalid('XX')])

    def test_duplicate_false(self):
        """Should return an error for every non-match (incl. duplicates)."""
        data = iter(['a1', 'b2', 'XX', 'XX', 'XX'])  # <- Multiple XX's.
        result = _require_regex(data, self.regex)
        self.assertEqual(list(result), [Invalid('XX'), Invalid('XX'), Invalid('XX')])

    def test_raised_error(self):
        """When an Exception is raised, it counts as False."""
        data = ['a1', 'b2', 30]  # <- Fails on 30 (re.search() expects a string).
        result = _require_regex(data, self.regex)
        self.assertEqual(list(result), [Invalid(30)])

    def test_notfound(self):
        result = _require_regex(NOTFOUND, self.regex)
        self.assertEqual(result, Invalid(None))


class TestRequireEquality(unittest.TestCase):
    def test_eq(self):
        """Should use __eq__() comparison, not __ne__()."""

        class EqualsAll(object):
            def __init__(_self):
                _self.times_called = 0

            def __eq__(_self, other):
                _self.times_called += 1
                return True

            def __ne__(_self, other):
                return NotImplemented

        data = ['A', 'A', 'A']
        requirement = EqualsAll()
        result = _require_equality(data, requirement)
        self.assertEqual(requirement.times_called, len(data))

    def test_all_true(self):
        result = _require_equality(iter(['A', 'A']), 'A')
        self.assertIsNone(result)

    def test_some_invalid(self):
        result = _require_equality(iter(['A', 'XX']), 'A')
        self.assertEqual(list(result), [Invalid('XX')])

    def test_some_deviation(self):
        result = _require_equality(iter([10, 11]), 10)
        self.assertEqual(list(result), [Deviation(+1, 10)])

    def test_invalid_and_deviation(self):
        result = _require_equality(iter([10, 'XX', 11]), 10)

        result = list(result)
        self.assertEqual(len(result), 2)
        self.assertIn(Invalid('XX'), result)
        self.assertIn(Deviation(+1, 10), result)

    def test_dict_comparison(self):
        data = iter([{'a': 1}, {'b': 2}])
        result = _require_equality(data, {'a': 1})
        self.assertEqual(list(result), [Invalid({'b': 2})])

    def test_broken_comparison(self):
        class BadClass(object):
            def __eq__(self, other):
                raise Exception("I have betrayed you!")

            def __hash__(self):
                return hash((self.__class__, 101))

        bad_instance = BadClass()

        data = iter([10, bad_instance, 10])
        result = _require_equality(data, 10)
        self.assertEqual(list(result), [Invalid(bad_instance)])


class TestRequireSingleEquality(unittest.TestCase):
    def test_eq(self):
        """Should use __eq__() comparison, not __ne__()."""

        class EqualsAll(object):
            def __init__(_self):
                _self.times_called = 0

            def __eq__(_self, other):
                _self.times_called += 1
                return True

            def __ne__(_self, other):
                return NotImplemented

        requirement = EqualsAll()
        result = _require_single_equality('A', requirement)
        self.assertEqual(requirement.times_called, 1)

    def test_all_true(self):
        result = _require_single_equality('A', 'A')
        self.assertIsNone(result)

    def test_some_invalid(self):
        result = _require_single_equality('XX', 'A')
        self.assertEqual(result, Invalid('XX', 'A'))

    def test_deviation(self):
        result = _require_single_equality(11, 10)
        self.assertEqual(result, Deviation(+1, 10))

    def test_invalid(self):
        result = _require_single_equality('XX', 10)
        self.assertEqual(result, Invalid('XX', 10))

    def test_dict_comparison(self):
        result = _require_single_equality({'a': 1}, {'a': 2})
        self.assertEqual(result, Invalid({'a': 1}, {'a': 2}))

    def test_broken_comparison(self):
        class BadClass(object):
            def __eq__(self, other):
                raise Exception("I have betrayed you!")

            def __hash__(self):
                return hash((self.__class__, 101))

        bad_instance = BadClass()
        result = _require_single_equality(bad_instance, 10)
        self.assertEqual(result, Invalid(bad_instance, 10))


class TestGetMsgAndFunc(unittest.TestCase):
    def setUp(self):
        self.multiple = ['A', 'B', 'A']
        self.single = 'B'

    def test_sequence(self):
        default_msg, require_func = _get_msg_and_func(['A', 'B'], ['A', 'B'])
        self.assertIsInstance(default_msg, str)
        self.assertEqual(require_func, _require_sequence)

    def test_set(self):
        default_msg, require_func = _get_msg_and_func(['A', 'B'], set(['A', 'B']))
        self.assertIsInstance(default_msg, str)
        self.assertEqual(require_func, _require_set)

    def test_callable(self):
        def myfunc(x):
            return True
        default_msg, require_func = _get_msg_and_func(['A', 'B'], myfunc)
        self.assertIn(myfunc.__name__, default_msg, 'message should include function name')
        self.assertEqual(require_func, _require_callable)

        mylambda = lambda x: True
        default_msg, require_func = _get_msg_and_func(['A', 'B'], mylambda)
        self.assertIn('<lambda>', default_msg, 'message should include function name')
        self.assertEqual(require_func, _require_callable)

        class MyClass(object):
            def __call__(_self, x):
                return True
        myinstance = MyClass()
        default_msg, require_func = _get_msg_and_func(['A', 'B'], myinstance)
        self.assertIn('MyClass', default_msg, 'message should include class name')
        self.assertEqual(require_func, _require_callable)

    def test_regex(self):
        myregex = re.compile('[AB]')
        default_msg, require_func = _get_msg_and_func(['A', 'B'], myregex)
        self.assertIn(repr(myregex.pattern), default_msg, 'message should include pattern')
        self.assertEqual(require_func, _require_regex)

    def test_equality(self):
        default_msg, require_func = _get_msg_and_func(['A', 'B'], 'A')
        self.assertIsInstance(default_msg, str)
        self.assertEqual(require_func, _require_equality)

        default_msg, require_func = _get_msg_and_func([{'a': 1}, {'a': 1}], {'a': 1})
        self.assertIsInstance(default_msg, str)
        self.assertEqual(require_func, _require_equality)

    def test_single_equality(self):
        default_msg, require_func = _get_msg_and_func('A', 'A')
        self.assertIsInstance(default_msg, str)
        self.assertEqual(require_func, _require_single_equality)

        default_msg, require_func = _get_msg_and_func({'a': 1}, {'a': 1})
        self.assertIsInstance(default_msg, str)
        self.assertEqual(require_func, _require_single_equality)


class TestApplyMappingRequirement(unittest.TestCase):
    """Calling _apply_mapping_requirement() should run the appropriate
    comparison function (internally) for each value-group and
    return the results as an iterable of key-value items.
    """
    def test_no_differences(self):
        # Sequence order.
        data = {'a': ['x', 'y']}
        result = _apply_mapping_requirement(data, {'a': ['x', 'y']})
        self.assertEqual(dict(result), {})

        # Set membership.
        data = {'a': ['x', 'y']}
        result = _apply_mapping_requirement(data, {'a': set(['x', 'y'])})
        self.assertEqual(dict(result), {})

        # Equality of single values.
        data = {'a': 'x', 'b': 'y'}
        result = _apply_mapping_requirement(data, {'a': 'x', 'b': 'y'})
        self.assertEqual(dict(result), {})

    def test_some_differences(self):
        # Sequence order.
        data = {'a': ['x', 'y']}
        result = _apply_mapping_requirement(data, {'a': ['x', 'z']})
        result = dict(result)
        self.assertTrue(len(result) == 1)
        self.assertEqual(result, {'a': {(1, 1): Invalid('y', 'z')}})

        # Set membership.
        data = {'a': ['x', 'x'], 'b': ['x', 'y', 'z']}
        result = _apply_mapping_requirement(data, {'a': set(['x', 'y']),
                                                   'b': set(['x', 'y'])})
        expected = {'a': [Missing('y')], 'b': [Extra('z')]}
        self.assertEqual(dict(result), expected)

        # Equality of single values.
        data = {'a': 'x', 'b': 10}
        result = _apply_mapping_requirement(data, {'a': 'j', 'b': 9})
        expected = {'a': Invalid('x', expected='j'), 'b': Deviation(+1, 9)}
        self.assertEqual(dict(result), expected)

        # Equality of multiple values.
        data = {'a': ['x', 'j'], 'b': [10, 9]}
        result = _apply_mapping_requirement(data, {'a': 'j', 'b': 9})
        expected = {'a': [Invalid('x')], 'b': [Deviation(+1, 9)]}
        self.assertEqual(dict(result), expected)

        # Equality of multiple values, missing key with single item.
        data = {'a': ['x', 'j'], 'b': [10, 9]}
        result = _apply_mapping_requirement(data, {'a': 'j', 'b': 9, 'c': 'z'})
        expected = {'a': [Invalid('x')], 'b': [Deviation(+1, 9)], 'c': Missing('z')}
        self.assertEqual(dict(result), expected)

        # Missing key, set membership.
        data = {'a': 'x'}
        result = _apply_mapping_requirement(data, {'a': 'x', 'b': set(['z'])})
        expected = {'b': [Missing('z')]}
        self.assertEqual(dict(result), expected)

    def test_comparison_error(self):
        # Sequence failure.
        nonsequence = {'a': 'x'}  # The value "x" is not a sequence
                                  # so comparing  it against the list
                                  # ['x', 'y'] should raise an error.
        with self.assertRaises(ValueError):
            result = _apply_mapping_requirement(nonsequence, {'a': ['x', 'y']})
            dict(result)  # Evaluate iterator.


class TestGetDifferenceInfo(unittest.TestCase):
    def test_mapping_requirement(self):
        """When *requirement* is a mapping, then *data* should also
        be a mapping. If *data* is not a mapping, an error should be
        raised.
        """
        mapping1 = {'a': 'x', 'b': 'y'}
        mapping2 = {'a': 'x', 'b': 'z'}

        info = _get_difference_info(mapping1, mapping1)
        self.assertIsNone(info)

        msg, diffs = _get_difference_info(mapping1, mapping2)
        self.assertTrue(_is_consumable(diffs))
        self.assertEqual(dict(diffs), {'b': Invalid('y', expected='z')})

        with self.assertRaises(TypeError):
            _get_difference_info(set(['x', 'y']), mapping2)

    def test_mapping_data(self):
        """"When *data* is a mapping but *requirement* is a non-mapping."""
        mapping = {'a': 'x', 'b': 'y'}

        x_or_y = lambda value: value == 'x' or value == 'y'
        result = _get_difference_info(mapping, x_or_y)
        self.assertIsNone(result)

        msg, diffs = _get_difference_info(mapping, 'x')  # <- string
        self.assertTrue(_is_consumable(diffs))
        self.assertEqual(dict(diffs), {'b': Invalid('y', expected='x')})

        msg, diffs = _get_difference_info(mapping, set('x'))  # <- set
        self.assertTrue(_is_consumable(diffs))
        self.assertEqual(dict(diffs), {'b': [Missing('x'), Extra('y')]})

    def test_nonmapping(self):
        """When neither *data* or *requirement* are mappings."""
        result = _get_difference_info(set(['x', 'y']), set(['x', 'y']))
        self.assertIsNone(result)

        msg, diffs = _get_difference_info(set(['x']), set(['x', 'y']))
        self.assertTrue(_is_consumable(diffs))
        self.assertEqual(list(diffs), [Missing('y')])
