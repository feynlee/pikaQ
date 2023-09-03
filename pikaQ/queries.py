# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/04_queries.ipynb.

# %% auto 0
__all__ = ['AliasedQuery', 'Table', 'QueryBase', 'Joiner', 'Selector', 'SelectQuery', 'UnionQuery', 'Query', 'Exists']

# %% ../nbs/04_queries.ipynb 2
from .utils import execute
from .terms import Field
import pikaQ.functions as fn

# %% ../nbs/04_queries.ipynb 4
class Table:
    """A class with star and as_ methods to be used as a Table/AliasesQuery in a query. Any other attribute will be treated as a field."""
    def __init__(self, name) -> None:
        self.name = self.alias = name
        self.get_sql = self.execute

    def as_(self, alias):
        self.alias = alias
        return self
    
    def star(self):
        return Field(f"{self.alias}.*")

    def __getattr__(self, __name: str):
        if __name.startswith('__'):
            raise AttributeError
        else:
            # if an alias is assigned, always use it as the table name when accessing a field
            return Field(f"{self.alias}.{__name}")

    def quoted_name(self, quote_char):
        name_list = self.name.split('.')
        name = '.'.join([f"{quote_char}{n}{quote_char}" for n in name_list])
        return name
    
    def execute(self, **kwargs):
        q = kwargs.get('quote_char', '') or ''
        quoted_name = self.quoted_name(q)
        if self.alias != self.name:
            return f"{quoted_name} as {q}{self.alias}{q}"
        else:
            return quoted_name


AliasedQuery = Table

# %% ../nbs/04_queries.ipynb 7
class QueryBase:
    """An empty query class to be inherited by all query classes. A convenient tool to make all query objects belong to this same class."""
    pass


class Joiner(QueryBase):
    """Join clause has to be followed by an on clause"""
    def __init__(self, select_query, query, how=None) -> None:
        self.select_query = select_query
        self.query = query
        self.how = how

    def on(self, condition):
        l = self.select_query.dic.get('join', [])
        l.append((self.query, self.how, condition))
        self.select_query.dic['join'] = l
        return self.select_query


class Selector(QueryBase):
    """Select clause could be followed by a distinct clause"""
    def __init__(self, select_query, *args) -> None:
        self.select_query = select_query
        self.select_query.dic['select'] = {"columns": list(args)}
        # add parse_select method to the select_query object
        self.select_query.parse_select = self.parse_select

    def __getattr__(self, __name: str):
        # selector inherits all methods from the SelectQuery object
        # so that the distinct method is optional
        # executing some of these methods can get back to the select_query object
        return getattr(self.select_query, __name)

    def parse_select(self, **kwargs):
        key = 'select'
        dic = self.dic[key]
        columns = dic['columns']
        columns = [execute(column, **kwargs) for column in columns]
        if dic.get('distinct'):
            return f"{key} distinct " + ', '.join(columns)
        else:
            return f"{key} " + ', '.join(columns)

    def distinct(self):
        self.select_query.dic['select']['distinct'] = True
        return self.select_query


class SelectQuery(QueryBase):
    """The class to construct a select query. It returns a `Joiner` object when called with the method join. It returns a `Selector` object when called with the method select."""
    keys_simple = ['from', 'groupby', 'orderby', 'where', 'having', 'limit']
    # the order to put together the final sql query
    sql_keys = ['with', 'select', 'from', 'join', 'where', 'groupby', 'having', 'orderby', 'limit']
    key_translation = {
        'groupby': 'group by',
        'orderby': 'order by'
    }

    def __init__(self) -> None:
        # the dictionary to store the queries for each clause
        self.dic = {}
        self.get_sql = self.execute

    def join(self, query, how=None):
        return Joiner(self, query, how)

    def select(self, *args):
        return Selector(self, *args)

    def __getattr__(self, __name):
        # Construct the corresponding method functions
        # remove the leading and trailing underscores
        __name = __name.strip('_').lower()
        # get the string after the first underscore
        key = '_'.join(__name.split('_')[1:])

        if __name.startswith('parse'):
            # Construct parse_xxx functions
            def inner(**kwargs):
                if key in ['from', 'where', 'having', 'limit']:
                    q = self.dic[key]
                    if isinstance(q, QueryBase):
                        return f"{self.key_translation.get(key, key)} ({execute(q, **kwargs)})"
                    else:
                        return f"{self.key_translation.get(key, key)} {execute(q, **kwargs)}"
                elif key in ['groupby', 'orderby']:
                    args = self.dic[key]
                    args = [execute(arg, **kwargs) for arg in args]
                    return f"{self.key_translation.get(key, key)} " + ', '.join(args)
                elif key == 'with':
                    s = self.dic[key]
                    qq = [f"{a} as (\n{execute(q, **kwargs)})" for q, a in s]
                    return f"{key} " + "\n\n, ".join(qq) + "\n"
                elif key == 'join':
                    l = self.dic[key]
                    parsed = []
                    for q, how, cond in l:
                        if how:
                            how = how + ' '
                        else:
                            how = ''
                        if isinstance(q, QueryBase):
                            sub_q = f"({execute(q, **kwargs)})"
                        else:
                            sub_q = execute(q, **kwargs)
                        parsed.append(f"{how}join {sub_q} on {execute(cond, **kwargs)}")
                    return '\n'.join(parsed)
                else:
                    raise AttributeError(f"parsing function for {key} is not defined!")
        else:
            # Construct other method functions
            if __name in ['from', 'where', 'having', 'limit']:
                def inner(q):
                    self.dic[__name] = q
                    return self
            elif __name in ['groupby', 'orderby']:
                def inner(*args):
                    self.dic[__name] = args
                    return self
            elif __name == 'with':
                def inner(query, alias):
                    l = self.dic.get('with', [])
                    l.append((query, alias))
                    self.dic['with'] = l
                    return self
            else:
                raise AttributeError(f"{__name} is not a valid attribute!")

        return inner

    def execute(self, **kwargs):
        dic_sql = {}

        for k, v in self.dic.items():
            dic_sql[k] = getattr(self, f"parse_{k}")(**kwargs)

        if missing_keys := [key for key in dic_sql if key not in self.sql_keys]:
            raise ValueError(f"The order of {missing_keys} in the final SQL are not specified in self.sql_keys!")

        sql = '\n'.join([dic_sql[key] for key in self.sql_keys if key in dic_sql])
        return sql
    
    def union(self, query):
        if not isinstance(query, QueryBase):
            raise TypeError(f"{query} is not an instance of QueryBase!")
        return UnionQuery(self, query, union_type='UNION')

    def __add__(self, query):
        return self.union(query)

    def union_all(self, query):
        if not isinstance(query, QueryBase):
            raise TypeError(f"{query} is not an instance of QueryBase!")
        return UnionQuery(self, query, union_type='UNION ALL')

    def __mul__(self, query):
        return self.union_all(query)


class UnionQuery(QueryBase):
    """The class to construct a union query."""
    def __init__(self, q1, q2, union_type='UNION') -> None:
        self.q1 = q1
        self.q2 = q2
        self.union_type = union_type

    def execute(self, **kwargs):
        return f"{execute(self.q1, **kwargs)} {self.union_type} {execute(self.q2, **kwargs)}"


class Query(QueryBase):
    """The main class to construct a query. It returns a `SelectQuery` object when called with the classmethod from_ or with_. One can extend this class to add more classmethods to construct different types of queries."""
    q = SelectQuery

    @classmethod
    def from_(cls, query):
        q = cls.q()
        q.dic['from'] = query
        return q

    @classmethod
    def with_(cls, query, alias):
        q = cls.q()
        q.dic['with'] = [(query, alias)]
        return q

# %% ../nbs/04_queries.ipynb 13
class Exists:
    """Exists statement"""
    def __init__(self, query:Query) -> None:
        super().__init__()
        self.query = query
        self.get_sql = self.execute

    def execute(self, **kwargs):
        return f"EXISTS ({self.query.get_sql(**kwargs)})"
