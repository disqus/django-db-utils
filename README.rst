(README needs mucho love)

attach_foreignkey
=================

Shortcut method which handles a pythonic LEFT OUTER JOIN.

::

    from dbutils.helpers import attach_foreignkey
    
    qs = list(Model.objects.all())
    
    attach_foreignkey(qs, Model.author)

queryset_to_dict
================

Shortcut method which stores a group of results as a dictionary
by the key you specify (or primary key by default).

::

    from dbutils.helpers import queryset_to_dict
    
    qs = Model.objects.all()
    
    queryset_to_dict(qs, 'author_id')


SkinnyQuerySet
==============

A QuerySet which eliminates the in-memory result cache.

::

    from dbutils.querysets import SkinnyQuerySet
    
    for foo in SkinnyQuerySet(Model):
        print foo


RangeQuerySet
=============

(See also: RangeQuerySetWrapper)

Iterates through a result set using MIN/MAX on primary key and stepping through.

Very efficient, but ORDER BY statements will not work.

::

    from dbutils.querysets import RangeQuerySet
    
    for foo in RangeQuerySet(Model):
        print foo


IterableQuerySetWrapper
=======================

Iterates through a QuerySet using limit and offset.

For efficiency use ``RangeQuerySetWrapper``.

::

    from dbutils.querysets import IterableQuerySetWrapper
    
    for foo in IterableQuerySetWrapper(Model.objects.all()):
        print foo