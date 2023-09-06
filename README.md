# pikaQ

<!-- WARNING: THIS FILE WAS AUTOGENERATED! DO NOT EDIT! -->

This library is heavily inspired by
[PyPika](https://github.com/kayak/pypika), so a lot of the syntax is
based on how PyPika works. Just like PyPika, PikaQ replaces handwritten
SQL queries with programmatic construction of queries. The main
difference is that pikaQ is designed to generate different SQL dialects
from the same code. This is done by using a common syntax that is then
translated to the specific dialect.

This library provides the core components and implementation for
constructing the `Select` query and the core mechanism for translating
it into different dialect. It does not offer complete coverage of SQL
syntax nor the detailed implementation of all the dialects. However, it
should be easy to extend the library to support more SQL syntax and
other types of queries you want to construct.

Validation of SQL correctness is not an explicit goal of PikaQ. You are
encouraged to check inputs you provide to PyPika or appropriately handle
errors raised from your SQL database - just as you would have if you
were writing SQL yourself.

## Install

``` sh
pip install pikaQ
```

## How to use

For example, if we want to write the same query in Spark SQL and AWS
Athena, we might encounter this problem: we have `ADD_MONTHS` function
in [Spark SQL](https://spark.apache.org/docs/2.3.0/api/sql/#add_months),
but in AWS Athena
([Presto](https://prestodb.io/docs/current/functions/datetime.html#interval-functions))
we don’t have this function.

We can define an `ADD_MONTHS` function in the following way:

``` python
from pikaQ.terms import custom_func
from pikaQ.queries import Query


@custom_func
def add_months(column, value, dialect='spark'):
    if dialect == 'athena':
        return f"DATE_ADD('month', {value}, {column})"
    elif dialect == 'spark':
        return f'ADD_MONTH({column}, {value})'
    else:
        raise ValueError(f'Unsupported dialect: {dialect}')


q = (Query.from_('table')
        .select('col1', add_months('col2', 3).as_('col2'))
)
```

Then we can generate the query for Spark SQL and AWS Athena:

``` python
print(q.get_sql(dialect='athena'))
```

    select col1, DATE_ADD('month', 3, col2) AS col2
    from table

``` python
print(q.get_sql(dialect='spark'))
```

    select col1, ADD_MONTH(col2, 3) AS col2
    from table

A more complex example to show how the syntax works:

``` python
from pikaQ.queries import Query, Table, Field, AliasedQuery
from pikaQ.terms import Case, Preceding, CURRENT_ROW
import pikaQ.functions as fn


a = Table('tbl1').as_('a')
b = Table('tbl2').as_('b')
s = AliasedQuery('s')
m = AliasedQuery('m')
v = AliasedQuery('v')

q0 = (Query
      .from_(a)
      .select(
         a.col1,
         a.col2,
         fn.Sum(a.col3).over(b.col2).rows(Preceding(3), CURRENT_ROW).as_('total'), 
         fn.RowNumber().over(b.col2).orderby(b.col4).as_('row_num')
      ).distinct()
      .where((Field('col2')-100>2) & (Field('col3')/9<=1))
      .orderby(b.col2)
)
q1 = (Query
      .from_(b)
      .select(b.col1, b.col2, fn.Avg(b.col3).as_('avg'))
      .groupby(b.col1, b.col2)
      .having(fn.Count(b.col3)>2)
)

q = (Query
     .with_(q0, 's')
     .with_(Query
         .from_(s)
         .select(s.star())
         .where(s.row_num == 1), 'm')
     .with_(q1, 'v')
     .from_('v')
     .join('m')
        .on(
            (v.col1 == m.col1) &
            (v.col2 == m.col2)
            )
     .select(
         v.col1, v.col2, v.avg,
         Case().when(m.total>100, 1).else_(0).as_('flag')
         )
)

print(q.get_sql())
```

    with s as (
    select distinct a.col1, a.col2, SUM(a.col3) OVER (PARTITION BY b.col2 ROWS BETWEEN 3 PRECEDING AND CURRENT_ROW) AS total, ROW_NUMBER() OVER (PARTITION BY b.col2 ORDER BY b.col4) AS row_num
    from tbl1 as a
    where col2 - 100 > 2 and col3 / 9 <= 1
    order by b.col2)

    , m as (
    select s.*
    from s
    where s.row_num = 1)

    , v as (
    select b.col1, b.col2, AVG(b.col3)
    from tbl2 as b
    group by b.col1, b.col2
    having COUNT(b.col3) > 2)

    select v.col1, v.col2, v.avg, CASE
    WHEN m.total > 100 THEN 1
    ELSE 0
    END AS flag
    from v
    join m on v.col1 = m.col1 and v.col2 = m.col2

For more syntax examples, please refer to the
[docs](https://feynlee.github.io/pikaQ/).

## Extension

One can use the core components and logic implemented in this library to
extend the functionality to support more SQL syntax and other types of
queries. For details of how to extend the
[`SelectQuery`](https://feynlee.github.io/pikaQ/queries.html#selectquery)
to support more clauses, please refer to the [Extending Query
section](https://feynlee.github.io/pikaQ/queries.html#extending-query)
of the docs.
