from django.db.models.manager import Manager
from django.db.models.query import QuerySet
from django.db.models.fields import AutoField, IntegerField
from django.db.models import Min, Max

from queryutils.helpers import attach_foreignkey

class QuerySetDoubleIteration(Exception):
    "A QuerySet was iterated over twice, you probably want to list() it."
    pass

# "Skinny" here means we use iterator by default, rather than
# ballooning in memory.
class SkinnyManager(Manager):
    def get_query_set(self):
        return SkinnyQuerySet(self.model, using=self._db)


class SkinnyQuerySet(QuerySet):
    """
    A QuerySet which eliminates the in-memory result cache.
    """
    def __len__(self):
        if getattr(self, 'has_run_before', False):
            raise TypeError("SkinnyQuerySet doesn't support __len__ after __iter__, if you *only* need a count you should use .count(), if you need to reuse the results you should coerce to a list and then len() that.")
        return super(SkinnyQuerySet, self).__len__()

    def __iter__(self):
        if self._result_cache is not None:
            # __len__ must have been run
            return iter(self._result_cache)

        has_run_before = getattr(self, 'has_run_before', False)
        if has_run_before:
            raise QuerySetDoubleIteration("This SkinnyQuerySet has already been iterated over once, you should assign it to a list if you want to reuse the data.")
        self.has_run_before = True

        return self.iterator()

    def list(self):
        return list(self)


class InvalidQuerySetError(ValueError): pass

class IterableQuerySetWrapper(object):
    """
    Iterates through a QuerySet using limit and offset.

    For efficiency use ``RangeQuerySetWrapper``.
    """
    def __init__(self, queryset, step=10000, limit=None):
        self.limit = limit
        if limit:
            self.step = min(limit, step)
        else:
            self.step = step
        self.queryset = queryset

    def __iter__(self):
        at = 0

        if isinstance(self.queryset, RangeQuerySet):
            extra_kwargs = {'bypass': True}
        else:
            extra_kwargs = {}

        results = list(self.queryset[at:at+self.step])
        while results and (not self.limit or at < self.limit):
            for result in results:
                yield result
            at += self.step
            results = list(self.queryset[at:at+self.step])

    def iterator(self):
        return iter(self)

class RangeQuerySet(SkinnyQuerySet):
    """
    See ``RangeQuerySetWrapper``
    """
    def __init__(self, model, step=10000, sorted=False, *args, **kwargs):
        super(SkinnyQuerySet, self).__init__(model, *args, **kwargs)
        self.step = step
        self.sorted = sorted

    def iterator(self, bypass=False):
        # Only execute if low mark is 0
        if not bypass and self.query.low_mark == 0 and not\
          (self.query.order_by or self.query.extra_order_by):
            # Clear the actual limit/offset
            high_mark = self.query.high_mark
            self.query.clear_limits()
            results = RangeQuerySetWrapper(self, step=self.step, limit=high_mark, sorted=self.sorted)
        elif not bypass:
            results = IterableQuerySetWrapper(self, step=self.step)
        else:
            results = super(RangeQuerySet, self).iterator()
        for result in results:
            yield result

class RangeQuerySetWrapper(object):
    """
    Iterates through a result set using MIN/MAX on primary key and stepping through.

    Very efficient, but ORDER BY statements will not work.
    """

    def __init__(self, queryset, step=10000, limit=None, min_id=None, max_id=None, sorted=False, select_related=[]):
        # Support for slicing
        if queryset.query.low_mark == 0 and not\
          (queryset.query.order_by or queryset.query.extra_order_by):
            limit = queryset.query.high_mark
            queryset.query.clear_limits()
        else:
            raise InvalidQuerySetError

        self.limit = limit
        if limit:
            self.step = min(limit, step)
        else:
            self.step = step
        self.queryset = queryset
        self.min_id, self.max_id = min_id, max_id
        self.sorted = sorted
        self.select_related = select_related

    def __iter__(self):
        pk = self.queryset.model._meta.pk
        if not isinstance(pk, (IntegerField, AutoField)):
            for result in iter(IterableQuerySetWrapper(self.queryset, self.step, self.limit)):
                yield result
        else:
            if self.min_id is not None and self.max_id is not None:
                at, max_id = self.min_id, self.max_id
            else:
                at = self.queryset.aggregate(Min('pk'), Max('pk'))
                max_id, at = at['pk__max'], at['pk__min']
                if self.min_id:
                    at = self.min_id
                if self.max_id:
                    max_id = self.max_id

            if not (at and max_id):
                return

            num = 0
            limit = self.limit or max_id

            if isinstance(self.queryset, RangeQuerySet):
                extra_kwargs = {'bypass': True}
            else:
                extra_kwargs = {}

            while at <= max_id and (not self.limit or num < self.limit):
                results = self.queryset.filter(id__gte=at, id__lte=min(at+self.step-1, max_id))
                if self.sorted:
                    results = results.order_by('id')
                results = results.iterator(**extra_kwargs)
                if self.select_related:
                    # we have to pull them all into memory to do the select_related
                    results = list(results)
                    for fkey in self.select_related:
                        if '__' in fkey:
                            fkey, related = fkey.split('__')
                        else:
                            related = []
                        attach_foreignkey(results, getattr(self.queryset.model, fkey, related))

                for result in results:
                    yield result
                    num += 1
                    if num >= limit:
                        break
                at += self.step
