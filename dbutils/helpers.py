from collections import defaultdict


def queryset_to_dict(qs, key='pk', singular=True):
    """
    Given a queryset will transform it into a dictionary based on ``key``.
    """
    if singular:
        result = {}
        for u in qs:
            result.setdefault(getattr(u, key), u)
    else:
        result = defaultdict(list)
        for u in qs:
            result[getattr(u, key)].append(u)
    return result


def distinct(l):
    """
    Given an iterable will return a list of all distinct values.
    """
    return list(set(l))


from django.db.models.fields.related import SingleRelatedObjectDescriptor


def attach_foreignkey(objects, field, related=[], database='default'):
    """
    Shortcut method which handles a pythonic LEFT OUTER JOIN.

    ``attach_foreignkey(posts, Post.thread)``

    Works with both ForeignKey and OneToOne (reverse) lookups.
    """
    is_foreignkey = isinstance(field, SingleRelatedObjectDescriptor)

    if not is_foreignkey:
        field = field.field
        accessor = '_%s_cache' % field.name
        model = field.rel.to
        lookup = 'pk'
        column = field.column
        key = lookup
    else:
        accessor = field.cache_name
        field = field.related.field
        model = field.model
        lookup = field.name
        column = 'pk'
        key = field.column

    # Ensure values are unique, do not contain already present values, and are not missing
    # values specified in select_related
    values = distinct(getattr(o, column) for o in objects if (related or getattr(o, accessor, False) is False))
    if not values:
        return

    qs = model.objects.filter(**{'%s__in' % lookup: values})\
              .using(database)
    if related:
        qs = qs.select_related(*related)
    queryset = queryset_to_dict(qs, key=key)
    for o in objects:
        setattr(o, accessor, queryset.get(getattr(o, column)))


def attach_foreignkeys(*object_sets, **kwargs):
    """
    Shortcut method which handles a pythonic LEFT OUTER JOIN. Allows you to attach the same object type
    to multiple different sets of data.

    ``attach_foreignkeys((posts, Post.author), (threads, Thread.creator), related=['profile'])``

    Works with only ForeignKeys
    """

    related = kwargs.get('related', [])
    database = kwargs.get('database', 'default')

    values = set()

    model = None

    for objects, field in object_sets:
        if not model:
            model = field.field.rel.to
        elif model != field.field.rel.to:
            raise ValueError('You cannot attach foreign keys that do not reference the same models (%s != %s)' % (model, field.field.rel.to))
        # Ensure values are unique, do not contain already present values, and are not missing
        # values specified in select_related
        values.update(distinct(getattr(o, field.field.column) for o in objects if (related or getattr(o, '_%s_cache' % field.field.name, False) is False)))

    if not values:
        return

    qs = model.objects.filter(pk__in=values).using(database)
    if related:
        qs = qs.select_related(*related)
    queryset = queryset_to_dict(qs)

    for objects, field in object_sets:
        for o in objects:
            setattr(o, '_%s_cache' % field.field.name, queryset.get(getattr(o, field.field.column)))
