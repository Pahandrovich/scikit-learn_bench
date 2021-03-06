# Copyright (C) 2020 Intel Corporation
#
# SPDX-License-Identifier: MIT

import argparse
from bench import (
    parse_args, measure_function_time, load_data, print_output, accuracy_score
)
import numpy as np
from cuml.svm import SVC


def get_optimal_cache_size(n_rows, dtype=np.double, max_cache=64):
    '''
    Get an optimal cache size for cuml.svm.SVC.

    Parameters
    ----------
    n_rows : int
        Number of rows in the dataset
    dtype : dtype-like, optional (default np.double)
        dtype to use for computing cache size
    max_cache : int, optional (default 64)
        Maximum cache size, in gigabytes
    '''

    byte_size = np.empty(0, dtype=dtype).itemsize
    optimal_cache_size_bytes = byte_size * (n_rows ** 2)
    one_gb = 2 ** 30
    max_cache_bytes = max_cache * one_gb
    if optimal_cache_size_bytes > max_cache_bytes:
        return max_cache_bytes
    else:
        return optimal_cache_size_bytes


parser = argparse.ArgumentParser(description='cuML SVM benchmark')

parser.add_argument('-C', dest='C', type=float, default=1.0,
                    help='SVM regularization parameter')
parser.add_argument('--kernel', choices=('linear', 'rbf'),
                    default='linear', help='SVM kernel function')
parser.add_argument('--maxiter', type=int, default=-1,
                    help='Maximum iterations for the iterative solver. '
                         '-1 means no limit.')
parser.add_argument('--gamma', type=float, default=None,
                    help='Parameter for kernel="rbf"')
parser.add_argument('--max-cache-size', type=int, default=8,
                    help='Maximum cache size, in gigabytes, for SVM.')
parser.add_argument('--tol', type=float, default=1e-3,
                    help='Tolerance passed to sklearn.svm.SVC')
params = parse_args(parser)

# Load data
X_train, X_test, y_train, y_test = load_data(params)

if params.gamma is None:
    params.gamma = 1.0 / X_train.shape[1]

cache_size_bytes = get_optimal_cache_size(X_train.shape[0],
                                          max_cache=params.max_cache_size)
params.cache_size_mb = cache_size_bytes / 1024**2
params.n_classes = y_train[y_train.columns[0]].nunique()

# Create our C-SVM classifier
clf = SVC(C=params.C, kernel=params.kernel, max_iter=params.maxiter,
          cache_size=params.cache_size_mb, tol=params.tol,
          gamma=params.gamma)

columns = ('batch', 'arch', 'prefix', 'function', 'threads', 'dtype', 'size',
           'kernel', 'cache_size_mb', 'C', 'sv_len', 'n_classes', 'accuracy',
           'time')

# Time fit and predict
fit_time, _ = measure_function_time(clf.fit, X_train, y_train, params=params)
params.sv_len = clf.support_.shape[0]

predict_time, y_pred = measure_function_time(
    clf.predict, X_train, params=params)
train_acc = 100 * accuracy_score(y_pred, y_train)

y_pred = clf.predict(X_test)
test_acc = 100 * accuracy_score(y_pred, y_test)

print_output(library='cuml', algorithm='svc',
             stages=['training', 'prediction'], columns=columns,
             params=params, functions=['SVM.fit', 'SVM.predict'],
             times=[fit_time, predict_time], accuracy_type='accuracy[%]',
             accuracies=[train_acc, test_acc], data=[X_train, X_train],
             alg_instance=clf)
