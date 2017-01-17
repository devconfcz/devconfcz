#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This script is used to normalize avatar photos
# It's based off a .sh script created by 
#   Jaroslav Kortus <jkortus@redhat.com>

import os
import sys
import subprocess

root_dir = sys.argv[1]
src_dir = os.path.join(root_dir, 'avatars-unprocessed')
out_root = os.path.join('avatars-processed-output')
bad_dir = os.path.join(root_dir, 'avatars-processed-bad')

if not os.path.exists(bad_dir):
    os.mkdir(bad_dir)

if not os.path.exists(out_root):
    os.mkdir(out_root)

def convert(size_x):
    size_y = size_x

    dir_name = '{}x{}'.format(size_x, size_y)
    out_dir = os.path.join(out_root, dir_name)

    if not os.path.exists(out_dir):
        os.mkdir(out_dir)

    files = os.listdir(src_dir)
    print('Processing {} files'.format(len(files)))

    cmd = 'convert {} -resize {}x{} -gravity South -background transparent -extent {}x{} -density 1x1 "{}"  || cp {} {}'

    for _file in files:
        if os.path.isdir(_file):
            continue
        _file = os.path.join(src_dir, _file)
        file_base = os.path.basename(_file)[:-4]
        out_ext = '{}.jpg'.format(dir_name)
        out_file = file_base + out_ext
        out_path = os.path.join(out_dir, out_file)
        bad_path = os.path.join(bad_dir, out_file)
        _run = cmd.format(_file, size_x, size_y, 
                          size_x, size_y, out_path, 
                          _file, bad_path)
        os.system(_run)


if len(sys.argv) >= 2:
    for arg in sys.argv[2:]:
        convert(arg)

