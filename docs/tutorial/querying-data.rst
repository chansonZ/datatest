
.. module:: datatest

.. meta::
    :description: Use datatest's DataSource, DataQuery, and DataResult
                  classes to handle the data under test.
    :keywords: datatest, DataSource, DataQuery, DataResult, working_directory


#############
Querying Data
#############

Datatest provides built-in classes for loading, querying, and
iterating over the data under test. Although users familiar with
other tools (Pandas, SQLAlchemy, etc.) should feel encouraged
to use whatever they find to be most productive.

..  To help use third-party data sources, datatest includes
    a number of helper functions to quickly load data into
    a variety of ORMs and DALs.

The following examples demonstrate datatest's :class:`DataSource`,
:class:`DataQuery`, and :class:`DataResult` classes. Users can
follow along and type the commands themselves at Python's
interactive prompt (``>>>``). For these examples, we will use
the following data:

    ===  ===  =====
    one  two  three
    ===  ===  =====
     a    x    100
     a    x    100
     b    x    100
     b    y    100
     c    y    100
     c    y    100
    ===  ===  =====


Loading Data
============

You can load the data from a CSV file (:download:`example.csv
</_static/example.csv>`) with :meth:`DataSource.from_csv`::

    >>> import datatest
    >>> source = datatest.DataSource.from_csv('example.csv')


Getting Field Names
===================

You can get a list of field names with :attr:`fieldnames
<DataSource.fieldnames>`::

    >>> source.fieldnames
    ['one', 'two', 'three']


.. sidebar:: The execute() Method

    In the following examples, we call :meth:`execute() <DataQuery.execute>`
    to eagerly evaluate the queries and display their results. In daily
    use, it's more efficient to leave off the "``.execute()``" part and
    validate the *un-executed* queries instead (which takes advantage of
    lazy evaluation).


Selecting Data
==============

Calling our source like a function returns a :class:`DataQuery`
for the specified field or fields.

Select elements from column **one** as a :py:class:`list`::

    >>> source(['one']).execute()
    ['a', 'a', 'b', 'b', 'c', 'c']

Select elements from column **one** as a :py:class:`set`::

    >>> source({'one'}).execute()
    {'a', 'b', 'c'}

The container type used in the selection determines the container
type returned in the result. You can think of the selection as a
template that describes the values and data types returned by the
query. Because set objects can not contain duplicates, the second
example above has only one element for each unique value in the
column.


Multiple Columns
----------------

Select elements from columns **one** and **two** as a list of
:py:class:`tuple` values::

    >>> source([('one', 'two')]).execute()  # Returns a list of tuples.
    [('a', 'x'),
     ('a', 'x'),
     ('b', 'x'),
     ('b', 'y'),
     ('c', 'y'),
     ('c', 'y')]

Select elements from columns **one** and **two** as a set of tuple
values::

    >>> source({('one', 'two')}).execute()  # Returns a set of tuples.
    {('a', 'x'),
     ('b', 'x'),
     ('b', 'y'),
     ('c', 'y')}

Compatible sequence and set types can be selected as inner and
outer containers as needed. A selection's outer container must
always hold a single element (a string or inner container).

In addition to lists, tuples and sets, users can also select
:py:class:`frozensets <frozenset>`, :py:func:`namedtuples
<collections.namedtuple>`, etc. However, normal object limitations
still apply---for example, sets can not contain mutable objects like
lists or other sets.


Groups of Columns
-----------------

Select groups of elements from column **one** that contain lists
of elements from column **two** as a :py:class:`dict`::

    >>> source({'one': ['two']}).execute()  # Grouped by key.
    {'a': ['x', 'x'],
     'b': ['x', 'y'],
     'c': ['y', 'y']}

Select groups of elements from columns **one** and **two** (using
a :py:class:`tuple`) that contain lists of elements from column
**three**::

    >>> source({('one', 'two'): ['three']}).execute()
    {('a', 'x'): ['100', '100'],
     ('b', 'x'): ['100'],
     ('b', 'y'): ['100'],
     ('c', 'y'): ['100', '100']}

When selecting groups of elements, you must provide a dictionary with
a single key-value pair. As before, the selection types determine the
result types, but keep in mind that dictionary keys must be `immutable
<http://docs.python.org/3/glossary.html#term-immutable>`_
(:py:class:`str`, :py:class:`tuple`, :py:class:`frozenset`, etc.).


Narrowing a Selection
=====================

Selections can be narrowed to rows that satisfy given keyword
arguments.

Narrow a selection to rows where column **two** equals "x"::

    >>> source([('one', 'two')], two='x').execute()
    [('a', 'x'),
     ('a', 'x'),
     ('b', 'x')]

The keyword column does not have to be in the selected result::

    >>> source(['one'], two='x').execute()
    ['a',
     'a',
     'b']

Narrow a selection to rows where column **one** equals "a" *or* "b"::

    >>> source([('one', 'two')], one=['a', 'b']).execute()
    [('a', 'x'),
     ('a', 'x'),
     ('b', 'x'),
     ('b', 'y')]

Narrow a selection to rows where column **one** equals "b" *and*
column **two** equals "y"::

    >>> source([('one', 'two')], one='b', two='y').execute()
    [('b', 'y')]  # Only 1 row matches these keyword conditions.


Additional Operations
=====================

:meth:`Sum <DataQuery.sum>` the values from column **three**::

    >>> source(['three']).sum().execute()
    600

Group by column **one** and sum the values from column **three** (for
each group)::

    >>> source({'one': ['three']}).sum().execute()
    {'a': 200,
     'b': 200,
     'c': 200}

Group by columns **one** and **two** and sum the values from column
**three**:

    >>> source({('one', 'two'): ['three']}).sum().execute()
    {('a', 'x'): 200,
     ('b', 'x'): 100,
     ('b', 'y'): 100,
     ('c', 'y'): 200}

Select :meth:`distinct <DataQuery.distinct>` values:

    >>> source(['one']).distinct().execute()
    ['a', 'b', 'c']

:meth:`Map <DataQuery.map>` values with a function:

    >>> def uppercase(x):
    ...     return str(x).upper()
    ...
    >>> source(['one']).map(uppercase).execute()
    ['A', 'A', 'B', 'B', 'C', 'C']


:meth:`Filter <DataQuery.filter>` values with a function:

    >>> def not_c(x):
    ...     return x != 'c'
    ...
    >>> source(['one']).filter(not_c).execute()
    ['a', 'a', 'b', 'b']

Multiple methods can be chained together:

    >>> def not_c(x):
    ...     return x != 'c'
    ...
    >>> def uppercase(x):
    ...     return str(x).upper()
    ...
    >>> source(['one']).filter(not_c).map(uppercase).execute()
    'AABB'