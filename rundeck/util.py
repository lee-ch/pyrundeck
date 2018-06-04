'''
Python module for the Rundeck API
'''
from __future__ import absolute_import, print_function, unicode_literals


def child2dict(el):
    '''
    Turns an ElementTree.Element's chidlren into a dict using the node names as dict keys
    and the node text as dict value.

    Returns a dictionary of element key(tag name)/value(node text) pairs

    :param el:
        ElementTree.Element
    '''
    return {c.tag: c.text for c in el}


def attr2dict(el):
    '''
    Turns an elements attrib dict into a dictionary and returns a dict of element attrib key/value
    pairs

    :param el:
        ElementTree.Element
    '''
    return {k: v for k, v in el.items()}


def node2dict(el):
    '''
    Combines both attr2dict and child2dict functions
    '''
    return dict(list(attr2dict(el).items()) + list(child2dict(el).items()))


def cull_kwargs(api_keys, kwargs):
    '''
    Strips the ``api_params`` from kwargs based on the list of api_keys

    Returns dictionary of the API params

    :param api_keys:
        (list, set, tuple) an iterable representing the keys of the key value
        pairs to pull out of kwargs

    :param kwargs:
        (dict) dictionary of keyword args
    '''
    # If keyword arg passed into the method calling ``cull_kwargs`` is in ``api_keys`` get the value
    # of ``kwargs`` and assign it to the ``api_key`` in a ``dict``
    return {k: kwargs.pop(k) for k in api_keys if k in kwargs}


def dict2argstring(arg_string):
    '''
    Converts an arg string dict into a string and return the string unchanged

    Returns arg string

    :param arg_string:
        (str, dict) argument string to pass to job - if str, will be passed as is,
        otherwise if it is a dict, will be converted to a compatible string
    '''
    if isinstance(arg_string, dict):
        return ' '.join(['-' + str(k) + ' ' + str(v) for k, v in arg_string.items()])
    else:
        return arg_string


try:
    if isinstance('', basestring):
        pass
except NameError:
    StringType = type('')
else:
    StringType = basestring
