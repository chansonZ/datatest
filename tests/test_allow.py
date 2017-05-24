# -*- coding: utf-8 -*-
import inspect
from . import _unittest as unittest
from datatest.utils import collections

from datatest.allow import BaseAllowance
from datatest.allow import ElementwiseAllowance
from datatest.allow import allow_key
from datatest.allow import allow_error
from datatest.allow import allow_args
from datatest.allow import allow_missing
from datatest.allow import allow_extra
from datatest.allow import allow_deviation
from datatest.allow import allow_percent_deviation
from datatest.allow import allow_specified
from datatest.allow import allow_limit
from datatest.allow import getvalue
from datatest.allow import getkey
from datatest.errors import ValidationError
from datatest.errors import DataError
from datatest.errors import Missing
from datatest.errors import Extra
from datatest.errors import Invalid
from datatest.errors import Deviation


class TestBaseAllowance(unittest.TestCase):
    def test_iterable_all_good(self):
        filterfalse = lambda iterable: list()  # <- empty list
        with BaseAllowance(filterfalse, None):  # <- Should pass without error.
            raise ValidationError('example error', [Missing('x')])

        filterfalse = lambda iterable: iter([])  # <- empty iterator
        with BaseAllowance(filterfalse, None):  # <- Should pass pass without error.
            raise ValidationError('example error', [Missing('x')])

    def test_iterable_some_bad(self):
        filterfalse = lambda iterable: [Missing('foo')]
        in_diffs = [Missing('foo'), Missing('bar')]

        with self.assertRaises(ValidationError) as cm:
            with BaseAllowance(filterfalse, None):
                raise ValidationError('example error', in_diffs)

        errors = cm.exception.errors
        self.assertEqual(list(errors), [Missing('foo')])

    def test_mismatched_types(self):
        """When given a non-mapping container, a non-mapping container
        should be returned for any remaining errors. Likewise, when
        given a mapping, a mapping should be returned for any remaining
        errors. If the intput and output types are mismatched, a
        TypeError should be raised.
        """
        # List input and dict output.
        errors_list =  [Missing('foo'), Missing('bar')]
        function = lambda iterable: {'a': Missing('foo')}  # <- dict type
        with self.assertRaises(TypeError):
            with BaseAllowance(function, None):
                raise ValidationError('example error', errors_list)

        # Dict input and list output.
        errors_dict =  {'a': Missing('foo'), 'b': Missing('bar')}
        function = lambda iterable: [Missing('foo')]  # <- list type
        with self.assertRaises(TypeError):
            with BaseAllowance(function, None):
                raise ValidationError('example error', errors_dict)

        # Dict input and list-item output.
        errors_dict =  {'a': Missing('foo'), 'b': Missing('bar')}
        function = lambda iterable: [('a', Missing('foo'))]  # <- list of items
        with self.assertRaises(ValidationError) as cm:
            with BaseAllowance(function, None):
                raise ValidationError('example error', errors_dict)

        errors = cm.exception.errors
        #self.assertIsInstance(errors, DictItems)
        self.assertEqual(dict(errors), {'a': Missing('foo')})

    def test_error_message(self):
        function = lambda iterable: iterable
        error = ValidationError('original message', [Missing('foo')])

        # No message.
        with self.assertRaises(ValidationError) as cm:
            with BaseAllowance(function):  # <- No 'msg' keyword!
                raise error
        message = cm.exception.message
        self.assertEqual(message, 'original message')

        # Test allowance message.
        with self.assertRaises(ValidationError) as cm:
            with BaseAllowance(function, msg='allowance message'):  # <- Uses 'msg'.
                raise error
        message = cm.exception.message
        self.assertEqual(message, 'allowance message: original message')


class TestElementwiseAllowanceFilterFalse(unittest.TestCase):
    def test_mapping_of_nongroups(self):
        iterable = {
            'a': Missing(1),
            'b': Extra(2),
            'c': Invalid(3),
        }
        def predicate(key, value):
            return (key == 'b') or isinstance(value, Invalid)

        elementwise = ElementwiseAllowance(predicate)
        result = elementwise.filterfalse(iterable)
        self.assertEqual(dict(result), {'a':  Missing(1)})

    def test_mapping_of_groups(self):
        """Key/value pairs should be passed to predicate for
        every element of an iterable group.
        """
        iterable = {
            'x': [
                Missing(1),
                Invalid(2),  # <- Matches predicate.
                Missing(3),
                Extra(4),    # <- Matches predicate.
            ],
            'y': [
                Missing(5),
                Extra(6),    # <- Matches predicate.
                Invalid(7),
            ],
            'z': [
                Extra(8),    # <- Matches predicate.
            ],
        }

        def predicate(key, value):
            if key == 'x' and isinstance(value, Invalid):
                return True
            if isinstance(value, Extra):
                return True
            return False

        elementwise = ElementwiseAllowance(predicate)
        result = elementwise.filterfalse(iterable)
        expected = {'x': [Missing(1), Missing(3)],
                    'y': [Missing(5), Invalid(7)]}
        self.assertEqual(dict(result), expected)

    def test_nonmapping(self):
        iterable = [Extra(1), Missing(2), Invalid(3)]

        def predicate(key, value):
            assert key is None  # <- For non-mapping, key is always None.
            return isinstance(value, Missing)

        elementwise = ElementwiseAllowance(predicate)
        result = elementwise.filterfalse(iterable)
        self.assertEqual(list(result), [Extra(1), Invalid(3)])


class TestElementwiseAllowances(unittest.TestCase):
    def test_ElementwiseAllowance(self):
        # Test mapping of errors.
        errors = {'a': Missing(1), 'b': Missing(2)}
        def function(key, error):
            return key == 'b' and isinstance(error, Missing)

        with self.assertRaises(ValidationError) as cm:
            with ElementwiseAllowance(function):  # <- Apply allowance!
                raise ValidationError('some message', errors)

        remaining_errors = cm.exception.errors
        self.assertEqual(dict(remaining_errors), {'a': Missing(1)})

        # Test non-mapping container of errors.
        errors = [Missing(1), Extra(2)]
        def function(key, error):
            assert key is None  # None when errors are non-mapping.
            return isinstance(error, Missing)

        with self.assertRaises(ValidationError) as cm:
            with ElementwiseAllowance(function):  # <- Apply allowance!
                raise ValidationError('some message', errors)

        remaining_errors = cm.exception.errors
        self.assertEqual(list(remaining_errors), [Extra(2)])

    def test_allow_key(self):
        # Test mapping of errors.
        errors = {'aaa': Missing(1), 'bbb': Missing(2)}
        def function(key):
            return key == 'aaa'

        with self.assertRaises(ValidationError) as cm:
            with allow_key(function):  # <- Apply allowance!
                raise ValidationError('some message', errors)

        remaining_errors = cm.exception.errors
        self.assertEqual(dict(remaining_errors), {'bbb': Missing(2)})

        # Test mapping of errors with composite keys.
        errors = {('a', 7): Missing(1), ('b', 7): Missing(2)}
        def function(letter, number):
            return letter == 'a' and number == 7

        with self.assertRaises(ValidationError) as cm:
            with allow_key(function):  # <- Apply allowance!
                raise ValidationError('some message', errors)

        remaining_errors = cm.exception.errors
        self.assertEqual(dict(remaining_errors), {('b', 7): Missing(2)})

        # Test non-mapping container of errors.
        errors = [Missing(1), Extra(2)]
        def function(key):
            assert key is None  # <- Always Non for non-mapping errors.
            return False  # < Don't match any errors.

        with self.assertRaises(ValidationError) as cm:
            with allow_key(function):  # <- Apply allowance!
                raise ValidationError('some message', errors)

        remaining_errors = cm.exception.errors
        self.assertEqual(list(remaining_errors), [Missing(1), Extra(2)])

    def test_allow_error(self):
        errors =  [Missing('X'), Missing('Y'), Extra('X')]
        def function(error):
            return isinstance(error, Missing)

        with self.assertRaises(ValidationError) as cm:
            with allow_error(function):  # <- Apply allowance!
                raise ValidationError('some message', errors)

        remaining_errors = cm.exception.errors
        self.assertEqual(list(remaining_errors), [Extra('X')])

    def test_allow_args(self):
        # Single argument.
        errors =  [Missing('aaa'), Missing('bbb'), Extra('bbb')]
        def function(arg):
            return arg == 'bbb'

        with self.assertRaises(ValidationError) as cm:
            with allow_args(function):  # <- Apply allowance!
                raise ValidationError('some message', errors)

        remaining_errors = cm.exception.errors
        self.assertEqual(list(remaining_errors), [Missing('aaa')])

        # Multiple arguments.
        errors =  [Deviation(1, 5), Deviation(2, 5)]
        def function(diff, expected):
            return diff < 2 and expected == 5

        with self.assertRaises(ValidationError) as cm:
            with allow_args(function):  # <- Apply allowance!
                raise ValidationError('some message', errors)

        remaining_errors = cm.exception.errors
        self.assertEqual(list(remaining_errors), [Deviation(2, 5)])

    def test_allow_missing(self):
        errors =  [Missing('X'), Missing('Y'), Extra('X')]

        with self.assertRaises(ValidationError) as cm:
            with allow_missing():  # <- Apply allowance!
                raise ValidationError('some message', errors)
        remaining_errors = cm.exception.errors
        self.assertEqual(list(remaining_errors), [Extra('X')])

    def test_allow_extra(self):
        errors =  [Extra('X'), Extra('Y'), Missing('X')]

        with self.assertRaises(ValidationError) as cm:
            with allow_extra():  # <- Apply allowance!
                raise ValidationError('some message', errors)
        remaining_errors = cm.exception.errors
        self.assertEqual(list(remaining_errors), [Missing('X')])


class TestComposabilityOfAllowances(unittest.TestCase):
    def test_or_operator(self):
        errors =  [Extra('X'), Missing('Y'), Invalid('Z')]
        with self.assertRaises(ValidationError) as cm:
            with allow_extra() | allow_missing():  # <- Compose with "|"!
                raise ValidationError('some message', errors)
        remaining_errors = cm.exception.errors
        self.assertEqual(list(remaining_errors), [Invalid('Z')])

    def test_and_operator(self):
        errors =  [Missing('X'), Extra('Y'), Missing('Z')]
        with self.assertRaises(ValidationError) as cm:
            is_x = lambda arg: arg == 'X'
            with allow_missing() & allow_args(is_x):  # <- Compose with "&"!
                raise ValidationError('some message', errors)
        remaining_errors = cm.exception.errors
        self.assertEqual(list(remaining_errors), [Extra('Y'), Missing('Z')])


class TestAllowSpecified(unittest.TestCase):
    def test_some_allowed(self):
        errors = [Extra('xxx'), Missing('yyy')]
        allowed = [Extra('xxx')]

        with self.assertRaises(ValidationError) as cm:
            with allow_specified(allowed):
                raise ValidationError('example error', errors)

        expected = [Missing('yyy')]
        actual = list(cm.exception.errors)
        self.assertEqual(expected, actual)

    def test_single_diff_without_container(self):
        errors = [Extra('xxx'), Missing('yyy')]
        allowed = Extra('xxx')  # <- Single diff, not in list.

        with self.assertRaises(ValidationError) as cm:
            with allow_specified(allowed):
                raise ValidationError('example error', errors)

        expected = [Missing('yyy')]
        actual = list(cm.exception.errors)
        self.assertEqual(expected, actual)

    def test_all_allowed(self):
        diffs = [Extra('xxx'), Missing('yyy')]
        allowed = [Extra('xxx'), Missing('yyy')]
        with allow_specified(allowed):
            raise ValidationError('example error', diffs)

    def test_duplicates(self):
        # Three of the exact-same differences.
        errors = [Extra('xxx'), Extra('xxx'), Extra('xxx')]

        # Only allow one of them.
        with self.assertRaises(ValidationError) as cm:
            allowed = [Extra('xxx')]
            with allow_specified(allowed):
                raise ValidationError('example error', errors)

        expected = [Extra('xxx'), Extra('xxx')]  # Expect two remaining.
        actual = list(cm.exception.errors)
        self.assertEqual(expected, actual)

        # Only allow two of them.
        with self.assertRaises(ValidationError) as cm:
            allowed = [Extra('xxx'), Extra('xxx')]
            with allow_specified(allowed):
                raise ValidationError('example error', errors)

        expected = [Extra('xxx')]  # Expect one remaining.
        actual = list(cm.exception.errors)
        self.assertEqual(expected, actual)

        # Allow all three.
        allowed = [Extra('xxx'), Extra('xxx'), Extra('xxx')]
        with allow_specified(allowed):
            raise ValidationError('example error', errors)

    def test_error_mapping_allowance_list(self):
        differences = {'foo': [Extra('xxx')], 'bar': [Extra('xxx'), Missing('yyy')]}
        allowed = [Extra('xxx')]

        with self.assertRaises(ValidationError) as cm:
            with allow_specified(allowed):
                raise ValidationError('example error', differences)

        expected = {'bar': [Missing('yyy')]}
        actual = cm.exception.errors
        self.assertEqual(expected, actual)

    def test_mapping_some_allowed(self):
        differences = {'foo': Extra('xxx'), 'bar': Missing('yyy')}
        allowed = {'foo': Extra('xxx')}

        with self.assertRaises(ValidationError) as cm:
            with allow_specified(allowed):
                raise ValidationError('example error', differences)

        expected = {'bar': Missing('yyy')}
        actual = cm.exception.errors
        self.assertEqual(expected, actual)

    def test_mapping_none_allowed(self):
        differences = {'foo': Extra('xxx'), 'bar': Missing('yyy')}
        allowed = {}

        with self.assertRaises(ValidationError) as cm:
            with allow_specified(allowed):
                raise ValidationError('example error', differences)

        actual = cm.exception.errors
        self.assertEqual(differences, actual)

    def test_mapping_all_allowed(self):
        errors = {'foo': Extra('xxx'), 'bar': Missing('yyy')}
        allowed = errors

        with allow_specified(allowed):  # <- Catches all differences, no error!
            raise ValidationError('example error', errors)

    def test_mapping_mismatched_types(self):
        error_list = [Extra('xxx'), Missing('yyy')]
        allowed_dict = {'foo': Extra('xxx'), 'bar': Missing('yyy')}

        regex = "'list' of errors cannot be matched.*requires non-mapping type"
        with self.assertRaisesRegex(ValueError, regex):
            with allow_specified(allowed_dict):
                raise ValidationError('example error', error_list)

    def test_integration(self):
        """This is a bit of an integration test."""
        differences = {'foo': Extra('xxx'), 'bar': Missing('zzz')}
        allowed = [Extra('xxx'), Missing('yyy')]

        with self.assertRaises(ValidationError) as cm:
            with allow_specified(allowed):
                raise ValidationError('example error', differences)
        actual = cm.exception.errors

        # Item-by-item assertion used to because Exception()
        # can not be tested for equality.
        self.assertIsInstance(actual, dict)
        self.assertEqual(set(actual.keys()), set(['foo', 'bar']))
        self.assertEqual(len(actual), 2)
        self.assertEqual(
            actual['foo'][0].args[0],
            "allowed errors not found: [Missing('yyy')]"
        )
        self.assertEqual(actual['bar'][0], Missing('zzz'))
        self.assertEqual(
            actual['bar'][1].args[0],
            "allowed errors not found: [Extra('xxx'), Missing('yyy')]"
        )


class TestAllowLimit(unittest.TestCase):
    """Test allow_limit() behavior."""
    def test_exceeds_limit(self):
        errors = [Extra('xxx'), Missing('yyy')]
        with self.assertRaises(ValidationError) as cm:
            with allow_limit(1):  # <- Allows only 1 but there are 2!
                raise ValidationError('example error', errors)

        remaining = list(cm.exception.errors)
        self.assertEqual(remaining, errors)

    def test_matches_limit(self):
        errors = [Extra('xxx'), Missing('yyy')]
        with allow_limit(2):  # <- Allows 2 and there are only 2.
            raise ValidationError('example error', errors)

    def test_under_limit(self):
        errors = [Extra('xxx'), Missing('yyy')]
        with allow_limit(3):  # <- Allows 3 and there are only 2.
            raise ValidationError('example error', errors)

    def test_dict_of_diffs_exceeds_and_match(self):
        errors = {
            'foo': [Extra('xxx'), Missing('yyy')],
            'bar': [Extra('zzz')],
        }
        with self.assertRaises(ValidationError) as cm:
            with allow_limit(1):  # <- Allows only 1 but there are 2!
                raise ValidationError('example error', errors)

        actual = cm.exception.errors
        expected = {'foo': [Extra('xxx'), Missing('yyy')]}
        self.assertEqual(dict(actual), expected)

    def test_bitwise_or_composition_under_limit(self):
        errors = [
            Extra('aaa'),
            Extra('bbb'),
            Missing('ccc'),
            Missing('ddd'),
            Missing('eee'),
        ]
        with allow_limit(2) | allow_missing():  # <- Limit of 2 or Missing.
            raise ValidationError('example error', errors)

    def test_bitwise_ror(self):
        """The right-side-or/__ror__ should be wired up to __or__."""
        errors = [
            Extra('aaa'),
            Extra('bbb'),
            Missing('ccc'),
            Missing('ddd'),
            Missing('eee'),
        ]
        with allow_missing() | allow_limit(2):  # <- On right-hand side!
            raise ValidationError('example error', errors)

    def test_bitwise_or_composition_over_limit(self):
        errors = [
            Extra('aaa'),
            Extra('bbb'),
            Extra('ccc'),
            Missing('ddd'),
            Missing('eee'),
        ]
        with self.assertRaises(ValidationError) as cm:
            with allow_limit(2) | allow_missing():
                raise ValidationError('example error', errors)

        # Returned errors *may* not be in the same order.
        actual = list(cm.exception.errors)
        self.assertEqual(actual, errors)

        # Test __ror__().
        with self.assertRaises(ValidationError) as cm:
            with allow_missing() | allow_limit(2):  # <- On right-hand side!
                raise ValidationError('example error', errors)

        # Returned errors *may* not be in the same order.
        actual = list(cm.exception.errors)
        self.assertEqual(actual, errors)

    def test_bitwise_and_composition_under_limit(self):
        errors = [Extra('xxx'), Missing('yyy'), Extra('zzz')]

        with self.assertRaises(ValidationError) as cm:
            is_extra = lambda x: isinstance(x, Extra)
            with allow_limit(4) & allow_extra():
                raise ValidationError('example error', errors)

        actual = list(cm.exception.errors)
        self.assertEqual(actual, [Missing('yyy')])

    def test_bitwise_rand(self):
        """The right-side-and/__rand__ should be wired up to __and__."""
        errors = [Extra('xxx'), Missing('yyy'), Extra('zzz')]

        # Make sure __rand__ (right-and) is wired-up to __and__.
        with self.assertRaises(ValidationError) as cm:
            is_extra = lambda x: isinstance(x, Extra)
            with allow_extra() & allow_limit(4):  # <- On right-hand side!
                raise ValidationError('example error', errors)

        actual = list(cm.exception.errors)
        self.assertEqual(actual, [Missing('yyy')])

    def test_bitwise_and_composition_over_limit(self):
        errors = [Extra('xxx'), Missing('yyy'), Extra('zzz')]
        with self.assertRaises(ValidationError) as cm:
            is_extra = lambda x: isinstance(x, Extra)
            with allow_limit(1) & allow_extra():  # <- Limit of 1 and is_extra().
                raise ValidationError('example error', errors)

        # Returned errors can be in different order.
        actual = list(cm.exception.errors)
        expected = [Missing('yyy'), Extra('xxx'), Extra('zzz')]
        self.assertEqual(actual, expected)

    def test_bitwise_and_composition_with_dict(self):
        errors = {
            'foo': [Extra('aaa'), Missing('bbb')],
            'bar': [Extra('ccc')],
            'baz': [Extra('ddd'), Extra('eee')],
        }
        with self.assertRaises(ValidationError) as cm:
            is_extra = lambda x: isinstance(x, Extra)
            with allow_limit(1) & allow_extra():
                raise ValidationError('example error', errors)

        actual = cm.exception.errors
        expected = {
            'foo': [Missing('bbb')],              # <- Missing not allowed at all.
            'baz': [Extra('ddd'), Extra('eee')],  # <- Returns everything when over limit.
        }
        self.assertEqual(dict(actual), expected)


class TestAllowDeviation(unittest.TestCase):
    """Test allow_deviation() behavior."""
    def test_method_signature(self):
        """Check for prettified default signature in Python 3.3 and later."""
        try:
            sig = inspect.signature(allow_deviation)
            parameters = list(sig.parameters)
            self.assertEqual(parameters, ['tolerance', 'msg'])
        except AttributeError:
            pass  # Python 3.2 and older use ugly signature as default.

    def test_tolerance_syntax(self):
        differences = {
            'aaa': Deviation(-1, 10),
            'bbb': Deviation(+3, 10),  # <- Not in allowed range.
        }
        with self.assertRaises(ValidationError) as cm:
            with allow_deviation(2):  # <- Allows +/- 2.
                raise ValidationError('example error', differences)

        remaining_errors = cm.exception.errors
        self.assertEqual(remaining_errors, {'bbb': Deviation(+3, 10)})

    def test_lowerupper_syntax(self):
        differences = {
            'aaa': Deviation(-1, 10),  # <- Not in allowed range.
            'bbb': Deviation(+3, 10),
        }
        with self.assertRaises(ValidationError) as cm:
            with allow_deviation(0, 3):  # <- Allows from 0 to 3.
                raise ValidationError('example error', differences)

        result_diffs = cm.exception.errors
        self.assertEqual({'aaa': Deviation(-1, 10)}, result_diffs)

    def test_single_value_allowance(self):
        differences = [
            Deviation(+2.9, 10),  # <- Not allowed.
            Deviation(+3.0, 10),
            Deviation(+3.0, 5),
            Deviation(+3.1, 10),  # <- Not allowed.
        ]
        with self.assertRaises(ValidationError) as cm:
            with allow_deviation(3, 3):  # <- Allows +3 only.
                raise ValidationError('example error', differences)

        result_diffs = list(cm.exception.errors)
        expected_diffs = [
            Deviation(+2.9, 10),
            Deviation(+3.1, 10),
        ]
        self.assertEqual(expected_diffs, result_diffs)

    def test_allowance_composition(self):
        with self.assertRaises(ValidationError) as cm:
            differences = {
                'aaa': Deviation(-1, 10),
                'bbb': Deviation(+2, 10),
                'ccc': Deviation(+2, 10),
                'ddd': Deviation(+3, 10),
            }

            def fn(key):
                return key in ('aaa', 'bbb', 'ddd')

            with allow_deviation(2) & allow_key(fn):  # <- composed with "&"!
                raise ValidationError('example error', differences)

        actual = cm.exception.errors
        expected = {
            'ccc': Deviation(+2, 10),  # <- Keyword value not allowed.
            'ddd': Deviation(+3, 10),  # <- Not in allowed range.
        }
        self.assertEqual(expected, actual)

    def test_invalid_tolerance(self):
        with self.assertRaises(AssertionError) as cm:
            with allow_deviation(-5):  # <- invalid
                pass
        exc = str(cm.exception)
        self.assertTrue(exc.startswith('tolerance should not be negative'))

    def test_empty_value_handling(self):
        # Test NoneType.
        with allow_deviation(0):  # <- Pass without failure.
            raise ValidationError('example error', [Deviation(None, 0)])

        with allow_deviation(0):  # <- Pass without failure.
            raise ValidationError('example error', [Deviation(0, None)])

        # Test empty string.
        with allow_deviation(0):  # <- Pass without failure.
            raise ValidationError('example error', [Deviation('', 0)])

        with allow_deviation(0):  # <- Pass without failure.
            raise ValidationError('example error', [Deviation(0, '')])

        # Test NaN (not a number) values.
        with self.assertRaises(ValidationError):  # <- NaN values should not be caught!
            with allow_deviation(0):
                raise ValidationError('example error', [Deviation(float('nan'), 0)])

        with self.assertRaises(ValidationError):  # <- NaN values should not be caught!
            with allow_deviation(0):
                raise ValidationError('example error', [Deviation(0, float('nan'))])

    # AN OPEN QUESTION: Should deviation allowances raise an error if
    # the maximum oberved deviation is _less_ than the given tolerance?


class TestAllowPercentDeviation(unittest.TestCase):
    """Test allow_percent_deviation() behavior."""
    def test_method_signature(self):
        """Check for prettified default signature in Python 3.3 and later."""
        try:
            sig = inspect.signature(allow_percent_deviation)
            parameters = list(sig.parameters)
            self.assertEqual(parameters, ['tolerance', 'msg'])
        except AttributeError:
            pass  # Python 3.2 and older use ugly signature as default.

    def test_tolerance_syntax(self):
        differences = [
            Deviation(-1, 10),
            Deviation(+3, 10),  # <- Not in allowed range.
        ]
        with self.assertRaises(ValidationError) as cm:
            with allow_percent_deviation(0.2):  # <- Allows +/- 20%.
                raise ValidationError('example error', differences)

        result_string = str(cm.exception)
        self.assertTrue(result_string.startswith('example error'))

        result_diffs = list(cm.exception.errors)
        self.assertEqual([Deviation(+3, 10)], result_diffs)

    def test_lowerupper_syntax(self):
        differences = {
            'aaa': Deviation(-1, 10),  # <- Not in allowed range.
            'bbb': Deviation(+3, 10),
        }
        with self.assertRaises(ValidationError) as cm:
            with allow_percent_deviation(0.0, 0.3):  # <- Allows from 0 to 30%.
                raise ValidationError('example error', differences)

        result_string = str(cm.exception)
        self.assertTrue(result_string.startswith('example error'))

        result_diffs = cm.exception.errors
        self.assertEqual({'aaa': Deviation(-1, 10)}, result_diffs)

    def test_single_value_allowance(self):
        differences = [
            Deviation(+2.9, 10),  # <- Not allowed.
            Deviation(+3.0, 10),
            Deviation(+6.0, 20),
            Deviation(+3.1, 10),  # <- Not allowed.
        ]
        with self.assertRaises(ValidationError) as cm:
            with allow_percent_deviation(0.3, 0.3):  # <- Allows +30% only.
                raise ValidationError('example error', differences)

        result_diffs = list(cm.exception.errors)
        expected_diffs = [
            Deviation(+2.9, 10),
            Deviation(+3.1, 10),
        ]
        self.assertEqual(expected_diffs, result_diffs)

    def test_allowance_composition(self):
        differences = {
            'aaa': Deviation(-1, 10),
            'bbb': Deviation(+2, 10),
            'ccc': Deviation(+2, 10),
            'ddd': Deviation(+3, 10),
        }
        with self.assertRaises(ValidationError) as cm:
            def keyfn(key):
                return key in ('aaa', 'bbb', 'ddd')

            with allow_percent_deviation(0.2) & allow_key(keyfn):  # <- Allows +/- 20%.
                raise ValidationError('example error', differences)

        result_set = cm.exception.errors
        expected_set = {
            'ccc': Deviation(+2, 10),  # <- Key value not 'aaa'.
            'ddd': Deviation(+3, 10),  # <- Not in allowed range.
        }
        self.assertEqual(expected_set, result_set)

    def test_invalid_tolerance(self):
        with self.assertRaises(AssertionError) as cm:
            with allow_percent_deviation(-0.5):  # <- invalid
                pass
        exc = str(cm.exception)
        self.assertTrue(exc.startswith('tolerance should not be negative'))

    def test_empty_value_handling(self):
        # Test NoneType.
        with allow_percent_deviation(0):  # <- Pass without failure.
            raise ValidationError('example error', [Deviation(None, 0)])

        with allow_percent_deviation(0):  # <- Pass without failure.
            raise ValidationError('example error', [Deviation(0, None)])

        # Test empty string.
        with allow_percent_deviation(0):  # <- Pass without failure.
            raise ValidationError('example error', [Deviation('', 0)])

        with allow_percent_deviation(0):  # <- Pass without failure.
            raise ValidationError('example error', [Deviation(0, '')])

        # Test NaN (not a number) values.
        with self.assertRaises(ValidationError):  # <- NaN values should not be caught!
            with allow_percent_deviation(0):
                raise ValidationError('example error', [Deviation(float('nan'), 0)])

        with self.assertRaises(ValidationError):  # <- NaN values should not be caught!
            with allow_percent_deviation(0):
                raise ValidationError('example error', [Deviation(0, float('nan'))])


class TestMsgIntegration(unittest.TestCase):
    """The 'msg' keyword is passed to to each parent class and
    eventually handled in the allow_iter base class. These tests
    do some sanity checking to make sure that 'msg' values are
    passed through the inheritance chain.
    """
    def test_allow_missing(self):
        # Check for modified message.
        with self.assertRaises(ValidationError) as cm:
            with allow_missing(msg='modified'):  # <- No msg!
                raise ValidationError('original', [Extra('X')])
        message = cm.exception.message
        self.assertEqual(message, 'modified: original')


class TestGetKeyDecorator(unittest.TestCase):
    def test_key_strings(self):
        @getkey  # <- Apply decorator!
        def func(key):
            return key == 'aa'

        self.assertTrue(func('aa', None))
        self.assertFalse(func('bb', None))

    def test_key_tuples(self):
        """Keys of non-string containers are unpacked before passing
        to function.
        """
        @getkey  # <- Apply decorator!
        def func(letter, number):  # <- Non-string iterable keys are unpacked.
            return letter == 'aa'

        self.assertTrue(func(('aa', 1), None))
        self.assertFalse(func(('bb', 2), None))
