# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/01_core.ipynb.

# %% auto 0
__all__ = ['CURRENT_ROW', 'quote_symbol', 'to_sql', 'exec', 'DelayedFunc', 'delayed_func', 'as_', 'DelayedPipeline', 'eval_type',
           'union2tuple', 'patch_to', 'patch_method', 'Field', 'ArithmeticExpression', 'Criteria', 'OverClause',
           'Preceding', 'Following']

# %% ../nbs/01_core.ipynb 1
import inspect

from functools import partial
from fastcore.basics import *
from fastcore.meta import *
from typing import Union

try: from types import UnionType
except ImportError: UnionType = None

# %% ../nbs/01_core.ipynb 4
def quote_symbol(quote):
    """generate quote symbol to use for tables and columns"""
    if type(quote) == str:
        return quote
    else:
        if quote == True:
            return '"'
        else:
            return ''


def to_sql(l):
    if type(l) == list:
        return '(' + ', '.join([f"{item}" if type(item) in (int, float) else f"'{item}'" for item in l]) + ')'
    else:
        raise ValueError(f"type {type(l)} for l is not implemented!")


def exec(obj, **kwargs):
    if hasattr(obj, 'exec'):
        return obj.exec(**kwargs)
    else:
        return str(obj)

# %% ../nbs/01_core.ipynb 6
def _exec(obj, **kwargs):
    if hasattr(obj, 'exec'):
        return obj.exec(**kwargs)
    else:
        return obj


class DelayedFunc:
    """Delay the execution of stored function until exec is run."""
    def __init__(self, func, args, kwargs, order=None) -> None: 
        store_attr()

    def exec(self, **kwargs):
        """keyword arguments can be overwritten with any provided new kwargs."""
        self.kwargs.update(kwargs)
        # recursively resolve all delayed functions
        args = (_exec(arg, **self.kwargs) for arg in self.args) 
        return self.func(*args, **self.kwargs)


def delayed_func(func):
    """return Delayed function"""
    def wrapper(*args, **kwargs):
        return DelayedFunc(func, args, kwargs)
    return wrapper

# %% ../nbs/01_core.ipynb 10
# class DelayedMethod:
#     """Delay the execution of a method until exec is run."""

#     def __init__(self,
#                  method, 
#                  _self,  # "self" for the Object the method belongs to
#                  args, 
#                  kwargs, 
#                  order=None
#                  ) -> None:
#         store_attr()

#     def exec(self, **kwargs):
#         """keyword arguments can be overwritten with any provided new kwargs."""
#         self.kwargs.update(kwargs)
#         # recursively resolve all delayed functions
#         args = (_exec(arg, **self.kwargs) for arg in self.args)
#         return self.method(self._self, *args, **self.kwargs)


# def delayed_method(func, order=None):
#     """wrap func in DelayedFunc and append it to self.dp"""
#     def wrapper(self, *args, **kwargs):
#         self.dp.append(DelayedMethod(func, self, args, kwargs, order=order))
#         return self
#     return wrapper


# def no_delay(self, func):
#     def inner(*args, **kwargs):
#         return func(self, *args, **kwargs)
#     return inner


def as_(self, alias):
    if self.res:
        self.alias = alias
        return self.res + f" AS {alias}"
    else:
        raise ValueError(f"self.res is {self.res}, can not append AS statement!")


class DelayedPipeline:
    """Execute delayed methods in self.dp in order when .exec is called."""
    dic = {
        'as_': {
            'order': None,
            'dialect': {
                'sql': as_
            }
        }
    }

    def __init__(self) -> None: 
        self.dp = []  # record all delayed functions
        self.ress = []  # save all intermediate results
        self.alias_allowed=True

    def __getattr__(self, attr):
        def _func(*args, dialect='sql', **kwargs):
            return self.dic[attr]['dialect'][dialect](self, *args, **kwargs)

        def wrapper(*args, **kwargs):
            dlf = DelayedFunc(_func, args, kwargs)
            dlf.order = self.dic[attr]['order']
            self.dp.append(dlf)
            return self
        return wrapper

    @property
    def res(self):
        if self.ress:
            return self.ress[-1]

    def _order_dp(self):
        dp_none = [d for d in self.dp if d.order is None]
        dp_order = [d for d in self.dp if d.order is not None]
        dp_order.sort(key=lambda x: x.order)
        self.dp = dp_order + dp_none

    def exec(self, **kwargs):
        self._order_dp()
        if self.dp:
            for d in self.dp:
                # save all intermediate steps in resolving the sql query
                self.ress.append(d.exec(**kwargs))
            self.dp = [] # clear the pipeline
        return self.res


def eval_type(t):
    "`eval` a type or collection of types, if needed, for annotations in py3.10+"
    if isinstance(t,str):
        if '|' in t: return Union[eval_type(tuple(t.split('|')))]
        return eval(t)
    if isinstance(t,(tuple,list)): return type(t)([eval_type(c) for c in t])
    return t


def union2tuple(t):
    if (getattr(t, '__origin__', None) is Union
        or (UnionType and isinstance(t, UnionType))): return t.__args__
    return t


def patch_to(func, dialect='sql'):
    ann = getattr(func, '__annotations__', None)
    nm = func.__name__
    cls = union2tuple(eval_type(next(iter(ann.values()))))
    if not isinstance(cls, (tuple,list)): cls=(cls,)
    for c_ in cls: 
        dic = getattr(c_, 'dic', None)
        if dic is not None:
            if nm not in dic:
                dic[nm] = {'order': None, 'dialect': {}}
            subdic = dic[nm]['dialect']
            subdic.update({dialect: func})
            dic[nm]['dialect'] = subdic
            c_.dic = dic
        else:
            raise ValueError(f"{c_} does not have class attribute `dic`, and can not be patched by path_method!")
    return func

        
def patch_method(func=None, dialect='sql'):
    if func is None: return partial(patch_method, dialect=dialect)
    return patch_to(func, dialect)

# %% ../nbs/01_core.ipynb 16
def _over(self, partition_by):
    return OverClause(self).over(partition_by)


class Field(DelayedPipeline):
    def __init__(self, name=None, window_func=True) -> None: 
        super().__init__()
        self.alias_allowed=True
        if window_func: 
            Field.over=_over
        if name:
            self.alias = name
            self.ress.append(name)
        self.sql = self.res
    
    def __add__(self, other):
        return ArithmeticExpression(self, '+', other)

    def __radd__(self, other):
        return ArithmeticExpression(other, '+', self)

    def __sub__(self, other):
        return ArithmeticExpression(self, '-', other)

    def __rsub__(self, other):
        return ArithmeticExpression(other, '-', self)

    def __mul__(self, other):
        return ArithmeticExpression(self, '*', other)
        
    def __rmul__(self, other):
        return ArithmeticExpression(other, '*', self)

    def __truediv__(self, other):
        return ArithmeticExpression(self, '/', other)

    def __rtruediv__(self, other):
        return ArithmeticExpression(other, '/', self)

    def __gt__(self, other):
        return Criteria(self, '>', other)

    def __ge__(self, other):
        return Criteria(self, '>=', other)
        
    def __eq__(self, other):
        return Criteria(self, '==', other)

    def __ne__(self, other):
        return Criteria(self, '!=', other)

    def __le__(self, other):
        return Criteria(self, '<=', other)

    def __lt__(self, other):
        return Criteria(self, '<', other)


class ArithmeticExpression(Field):
# class ArithmeticExpression:
    add_order = ["+", "-"]

    def __init__(self, this, op, other) -> None:
        super().__init__()
        self.this, self.op, self.other = this, op, other

    def __add__(self, other):
        return ArithmeticExpression(self, '+', other)

    def __radd__(self, other):
        return ArithmeticExpression(other, '+', self)

    def __sub__(self, other):
        return ArithmeticExpression(self, '-', other)

    def __rsub__(self, other):
        return ArithmeticExpression(other, '-', self)

    def __mul__(self, other):
        return ArithmeticExpression(self, '*', other)
        
    def __rmul__(self, other):
        return ArithmeticExpression(other, '*', self)

    def __truediv__(self, other):
        return ArithmeticExpression(self, '/', other)

    def __rtruediv__(self, other):
        return ArithmeticExpression(other, '/', self)
    
    def __gt__(self, other):
        return Criteria(self, '>', other)

    def __ge__(self, other):
        return Criteria(self, '>=', other)
        
    def __eq__(self, other):
        return Criteria(self, '==', other)

    def __ne__(self, other):
        return Criteria(self, '!=', other)

    def __le__(self, other):
        return Criteria(self, '<=', other)

    def __lt__(self, other):
        return Criteria(self, '<', other)

    def left_needs_parens(self, left_op, curr_op) -> bool:
        """
        Returns true if the expression on the left of the current operator needs to be enclosed in parentheses.
        :param current_op:
            The current operator.
        :param left_op:
            The highest level operator of the left expression.
        """
        if left_op is None or curr_op in self.add_order:
            # If the left expression is a single item.
            # or if the current operator is '+' or '-'.
            return False
        
        # The current operator is '*' or '/'. 
        # If the left operator is '+' or '-', we need to add parentheses:
        # e.g. (A + B) / ..., (A - B) / ...
        # Otherwise, no parentheses are necessary:
        # e.g. A * B / ..., A / B / ...
        return left_op in self.add_order

    def right_needs_parens(self, curr_op, right_op) -> bool:
        """
        Returns true if the expression on the right of the current operator needs to be enclosed in parentheses.
        :param current_op:
            The current operator.
        :param right_op:
            The highest level operator of the right expression.
        """
        if right_op is None:
            # If the right expression is a single item.
            return False
        # If the right operator is '+' or '-', we always add parentheses:
        # e.g. ... - (A + B), ... - (A - B), ... + (A + B)
        # Otherwise, no parentheses are necessary:
        # e.g. ... - A / B, ... - A * B
        return right_op in self.add_order

    def exec(self, **kwargs):
        if self.this.__class__ is ArithmeticExpression:
            this = self.this.exec(**kwargs)
            this = f"({this})" if self.left_needs_parens(self.this.op, self.op) else this
        elif getattr(self.this, 'exec', None):
            this = self.this.exec(**kwargs)
        else:
            this = str(self.this)

        if self.other.__class__ is ArithmeticExpression:
            other = self.other.exec(**kwargs)
            other = f"({other})" if self.right_needs_parens(self.op, self.other.op) else other
        elif getattr(self.other, 'exec', None):
            other = self.other.exec(**kwargs)
        else:
            other = str(self.other)
        return f"{this} {self.op} {other}"


class Criteria(Field):
    compose_ops = ('and', 'or')

    def __init__(self, this, op, other) -> None:
        super().__init__()
        self.this, self.op, self.other = this, op, other
        self.add_parentheses = False

    def compose_criteria(self, op, other):
        if other.__class__ is Criteria:
            if self.op in self.compose_ops and op in self.compose_ops and self.op != op:
                self.add_parentheses = True
            if other.op in self.compose_ops and op in self.compose_ops and other.op != op:
                other.add_parentheses = True
        return Criteria(self, op, other)

    @staticmethod
    def resolve(obj, **kwargs):
        if obj.__class__ is Criteria:
            obj_c = obj.exec(**kwargs)
            obj_c = f"({obj_c})" if obj.add_parentheses == True else obj_c
        elif getattr(obj, 'exec', None):
            obj_c = obj.exec(**kwargs)
        else:
            obj_c = str(obj)
        return obj_c
    
    def exec(self, **kwargs):
        this = self.resolve(self.this, **kwargs)
        other = self.resolve(self.other, **kwargs)
        return f"{this} {self.op} {other}"

    def __and__(self, __o):
        return self.compose_criteria('and', __o)

    def __or__(self, __o):
        return self.compose_criteria('or', __o)


class OverClause:
    def __init__(self, expression) -> None:
        if not (isinstance(expression, Field) or type(expression) is str):
            raise ValueError(f"Expression has to be of the Field type (including ArithmeticExpression)!!")
        self.expr = expression
        self.alias = None
        self.rows_flag = False
        self.range_flag = False
        self.d = {}

    def over(self, q):
        self.d['PARTITION BY'] = q
        return self

    def orderby(self, q):
        self.d['ORDER BY'] = q
        return self

    def _check_rows_or_range(self):
        if self.rows_flag==True: 
            raise ValueError(f"ROWS already set!")
        if self.range_flag==True:
            raise ValueError(f"RANGE already set!")

    def rows(self, start, end):
        self._check_rows_or_range()
        self.rows = True
        self.d['ROWS'] = (start, end)
        return self

    def range(self, start, end):
        self._check_rows_or_range()
        self.range = True
        self.d['RANGE'] = (start, end)
        return self

    def as_(self, alias):
        self.alias = alias
        return self

    def _resolve_over_statement(self, **kwargs):
        sql = []
        for k in ['PARTITION BY', 'ORDER BY', 'ROWS', 'RANGE']:
            if k in self.d:
                if k in ['PARTITION BY', 'ORDER BY']:
                    rslvd = f"{k} {exec(self.d[k], **kwargs)}"
                else:
                    start, end = self.d[k]
                    rslvd = f"{k} BETWEEN {exec(start, **kwargs)} AND {exec(end, **kwargs)}"
                sql.append(rslvd)
        return f"{exec(self.expr, **kwargs)} OVER ({' '.join(sql)})"

    def exec(self, **kwargs):
        sql = self._resolve_over_statement(**kwargs)
        if self.alias:
            return f"{sql} AS {self.alias}"
        else:
            return sql


class Preceding:
    def __init__(self, N=None) -> None:
        self.N = N

    def exec(self, **kwargs):
        if self.N:
            return f"{self.N} PRECEDING"
        else:
            return "UNBOUNDED PRECEDING"


class Following:
    def __init__(self, N=None) -> None:
        self.N = N

    def exec(self, **kwargs):
        if self.N:
            return f"{self.N} FOLLOWING"
        else:
            return "UNBOUNDED FOLLOWING"


CURRENT_ROW = "CURRENT_ROW"


