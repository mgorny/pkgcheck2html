#!/usr/bin/env python
# vim:se fileencoding=utf8 :
# (c) 2015-2019 Michał Górny
# 2-clause BSD license

import argparse
import io
import json
import os
import os.path
import sys
import lxml.etree


class ClassMapping(object):
    def __init__(self, class_mapping, excludes):
        self._class_mapping = class_mapping
        self._excludes = excludes

    def map(self, el):
        cls, cat, pkg, ver = (el.findtext(x, '')
                for x in ('class', 'category', 'package', 'version'))
        if cls in self._excludes.get(cat, {}).get(pkg, {}).get(ver, []):
            return ''
        return self._class_mapping.get(cls, '')


class Result(object):
    def __init__(self, el, class_mapper):
        self._el = el
        self._class_mapper = class_mapper

    def __getattr__(self, key):
        return self._el.findtext(key) or ''

    @property
    def css_class(self):
        return self._class_mapper.map(self._el)


def result_sort_key(r):
    return (r.category, r.package, r.version, getattr(r, 'class'))


def get_results(input_paths, class_mapping, excludes):
    mapper = ClassMapping(class_mapping, excludes)
    for input_path in input_paths:
        if input_path == '-':
            input_path = sys.stdin
        checks = lxml.etree.parse(input_path).getroot()
        for r in checks:
            yield Result(r, mapper)


def split_result_group(it):
    for r in it:
        if not r.category:
            yield ((), r)
        elif not r.package:
            yield ((r.category,), r)
        elif not r.version:
            yield ((r.category, r.package), r)
        else:
            yield ((r.category, r.package, r.version), r)


def group_results(it, level = 3):
    prev_group = ()
    prev_l = []

    for g, r in split_result_group(it):
        if g[:level] != prev_group:
            if prev_l:
                yield (prev_group, prev_l)
            prev_group = g[:level]
            prev_l = []
        prev_l.append(r)
    yield (prev_group, prev_l)


def find_of_class(it, cls, level = 2):
    for g, r in group_results(it, level):
        for x in r:
            if x.css_class in cls:
                yield g
                break


def output_borked(f, results):
    for g in results:
        f.write('%s\n' % ('/'.join(g[:2]) if g else 'global'))


def main(*args):
    p = argparse.ArgumentParser()
    p.add_argument('-e', '--error', action='store_true',
            help='Output error class reports (the default unless other option'
                + ' is specified, can be combined with --staging --warning)')
    p.add_argument('-o', '--output', default='-',
            help='Output borked list file')
    p.add_argument('-s', '--staging', action='store_true',
            help='Output staging class reports (can be combined with --warning and --error)')
    p.add_argument('-w', '--warning', action='store_true',
            help='Output warning class reports (can be combined with --staging and --error)')
    p.add_argument('-x', '--excludes',
            help='JSON file specifying existing exceptions to staging warnings')
    p.add_argument('files', nargs='+',
            help='Input XML files')
    args = p.parse_args(args)

    conf_path = os.path.join(os.path.dirname(__file__), 'pkgcheck2html.conf.json')
    with io.open(conf_path, 'r', encoding='utf8') as f:
        class_mapping = json.load(f)

    excludes = {}
    if args.excludes is not None:
        with open(args.excludes) as f:
            excludes = json.load(f)

    cls = set()
    if args.error:
        cls.add('err')
    if args.staging:
        cls.add('staging')
    if args.warning:
        cls.add('warn')
    # default to error
    if not cls:
        cls.add('err')

    results = sorted(get_results(args.files, class_mapping, excludes),
                     key=result_sort_key)
    # filter and group the results
    results = find_of_class(results, cls)

    if args.output == '-':
        output_borked(sys.stdout, results)
    else:
        with open(args.output, 'w') as f:
            output_borked(f, results)


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:]))
