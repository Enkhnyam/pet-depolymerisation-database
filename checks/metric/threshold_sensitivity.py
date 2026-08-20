"""Answers 'did you tune the thresholds until the number looked good?'. If the reported
settings sit on a plateau rather than a peak, they were not cherry-picked."""
from _setup import *

def sweep(setting, values):
    frame = pd.DataFrame({v: totals(**{setting: v}) for v in values}).T
    frame.index.name = setting
    return frame[["f1", "precision", "recall"]]

show(f"acceptance cutoff (using {ACCEPT:.2f})", sweep("accept", [.2, .25, .3, .35, .4, .5]))
show(f"catalyst similarity (using {CATALYST:.2f})", sweep("catalyst", [.4, .5, .6, .7, .8, .9, 1.]))
show(f"numeric tolerance (using {TOLERANCE:.2f})", sweep("tolerance", [.05, .1, .2, .3, .5]))
