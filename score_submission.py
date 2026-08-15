#!/usr/bin/env python3
"""Check a Synth-Sig Challenge submission: file format and in-sample MAE.

    ./score_submission.py my_submission.csv
"""
import argparse
import os
import sys
import warnings
from datetime import datetime, timedelta, timezone

import numpy as np

X_MIN, X_MAX = 394, 8000
N_ROWS = X_MAX - X_MIN + 1
GATE = 0.02
DEADLINE = datetime(2026, 9, 30, 23, 59, tzinfo=timezone(timedelta(hours=1)))


def deadline_note():
    days = (DEADLINE - datetime.now(timezone.utc)).days
    stamp = DEADLINE.strftime('%Y-%m-%d %H:%M CET')
    if days < 0:
        return f'deadline {stamp} has passed'
    return f'{days} days left until the deadline, {stamp}'


def load_two_columns(path):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        data = read_numbers(path)
    return data[:, 0], data[:, 1]


def read_numbers(path):
    try:
        data = np.loadtxt(path)
    except ValueError as exc:
        raise ValueError(f'{path}: could not be read as numbers ({exc})') from None
    data = np.atleast_2d(data)
    if data.size == 0:
        raise ValueError(f'{path}: file is empty')
    if data.shape[1] != 2:
        raise ValueError(f'{path}: expected 2 columns, found {data.shape[1]}')
    return data


def validate(x, y):
    """Return a list of problems with the submission."""
    problems = []
    if not np.all(np.isfinite(x)):
        return [f'{int((~np.isfinite(x)).sum())} non-finite x values']
    if not np.all(x == np.round(x)):
        problems.append('x values are not integers')
    xi = x.astype(np.int64)
    duplicates = len(xi) - len(np.unique(xi))
    if duplicates:
        problems.append(f'{duplicates} duplicate x values')
    expected = np.arange(X_MIN, X_MAX + 1)
    missing = np.setdiff1d(expected, xi)
    extra = np.setdiff1d(xi, expected)
    if len(missing):
        problems.append(f'{len(missing)} missing x values, '
                        f'first ones {missing[:3].tolist()}')
    if len(extra):
        problems.append(f'{len(extra)} x values outside {X_MIN}...{X_MAX}')
    if not np.all(np.isfinite(y)):
        problems.append(f'{int((~np.isfinite(y)).sum())} non-finite y values')
    return problems


def mae_against(reference_csv, x_sub, y_sub):
    x_ref, y_ref = load_two_columns(reference_csv)
    lookup = dict(zip(x_sub.astype(np.int64), y_sub))
    y_model = np.array([lookup[int(xr)] for xr in x_ref])
    return float(np.mean(np.abs(y_model - y_ref))), len(x_ref)


def verdict(value):
    return 'PASS' if value <= GATE else 'FAIL'


def apply_style(mpl):
    """Plain dark style."""
    mpl.rcParams.update({
        'text.usetex': False,
        'figure.facecolor': '#0a0a0a', 'axes.facecolor': '#1a1a1a',
        'axes.edgecolor': '#CCCCCC', 'axes.labelcolor': '#CCCCCC',
        'text.color': '#CCCCCC', 'xtick.color': '#CCCCCC',
        'ytick.color': '#CCCCCC', 'grid.color': '#666666', 'font.size': 12,
        'savefig.facecolor': '#0a0a0a', 'savefig.edgecolor': '#0a0a0a'})


def plot_submission(x, y, in_sample_csv, scores):
    """Draw the published data and the submission."""
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    apply_style(mpl)

    x_in, y_in = load_two_columns(in_sample_csv)

    label = 'Submission'
    if scores:
        label += ' — ' + ', '.join(f'{k} {v:.4f}' for k, v in scores.items())

    fig, (ax_full, ax_zoom) = plt.subplots(
        2, 1, figsize=(13, 10),
        gridspec_kw={'height_ratios': [1, 1], 'hspace': 0.30})
    for ax, x_lo in ((ax_full, X_MIN), (ax_zoom, 5000)):
        ax.plot(x_in, y_in, color='orange', linewidth=0.9, label='Published data')
        ax.plot(x, y, color='#2196F3', linestyle='--', linewidth=1.0, label=label)
        ax.axvline(x_in.max(), color='#AAAAAA', linestyle=':', linewidth=1.0)
        ax.set_xlim(x_lo, X_MAX)
        visible = [yy[(xx >= x_lo) & (xx <= X_MAX)]
                   for xx, yy in ((x_in, y_in), (x, y))]
        visible = np.concatenate([v for v in visible if len(v)])
        margin = 0.08 * max(visible.max() - visible.min(), 1e-9)
        ax.set_ylim(visible.min() - margin, visible.max() + margin)
        ax.set_xlabel('x')
        ax.set_ylabel('y')
        ax.grid(True, ls='--', lw=0.5)
        ax.legend(loc='upper right', fontsize=9, facecolor='#1A1A1A',
                  edgecolor='#808080', labelcolor='#E0E0E0')
    ax_full.set_title('Full range', fontsize=12, pad=4)
    ax_zoom.set_title('Zoom on the extrapolation', fontsize=12, pad=4)

    plt.suptitle('Synth-Sig Challenge — Submission Check',
                 color='#CCCCCC', fontsize=14, y=0.985, fontweight='bold')
    plt.figtext(0.5, 0.945, deadline_note(), ha='center', va='top',
                color='#999999', fontsize=10)
    plt.subplots_adjust(top=0.91, bottom=0.06, left=0.07, right=0.95, hspace=0.30)
    plt.show()


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('submission', help='CSV with two columns, x = 394...8000')
    parser.add_argument('--data-dir', default=os.path.dirname(os.path.abspath(__file__)),
                        help='directory holding synth-sig.csv')
    parser.add_argument('--plot', action='store_true',
                        help='open a window showing the published data and your '
                             'submission')
    args = parser.parse_args()

    try:
        x, y = load_two_columns(args.submission)
    except ValueError as exc:
        print(f'INVALID: {exc}')
        return 1
    print(f'{args.submission}: {len(x)} rows, expected {N_ROWS}')
    print(deadline_note())

    problems = validate(x, y)
    if problems:
        print('INVALID: ' + '; '.join(problems))
        return 1
    print('format OK')

    in_sample_csv = os.path.join(args.data_dir, 'synth-sig.csv')
    mae_in, n_in = mae_against(in_sample_csv, x, y)
    print(f'  in-sample MAE    ({n_in} points): {mae_in:.6f}   {verdict(mae_in)}')

    if mae_in <= GATE:
        print(f'\nIn-sample is within the limit of {GATE}.')
    else:
        print(f'\nNOT QUALIFIED — in-sample above the limit of {GATE}.')

    if args.plot:
        plot_submission(x, y, in_sample_csv,
                        {'in-sample MAE': mae_in})
    return 0


if __name__ == '__main__':
    sys.exit(main())
