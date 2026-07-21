import numpy as np

from vowelchemy import sample_data, trajectories
from vowelchemy.schema import ColumnSchema


def test_detects_trajectory_data():
    tracks, _ = sample_data.make_demo_tracks(n_per_cell=1)
    schema = ColumnSchema.detect(tracks)
    assert trajectories.is_trajectory_data(tracks, schema)
    track = trajectories.TrackSchema.detect(tracks, schema)
    assert track is not None and track.time == "prop_time"


def test_point_data_is_not_trajectory():
    tokens, _ = sample_data.make_demo_dataset(n_per_cell=1, tokens_per_vowel=5)
    schema = ColumnSchema.detect(tokens)
    assert not trajectories.is_trajectory_data(tokens, schema)


def test_mean_trajectories_shape_and_movement():
    tracks, _ = sample_data.make_demo_tracks(n_per_cell=1)
    schema = ColumnSchema.detect(tracks)
    track = trajectories.TrackSchema.detect(tracks, schema)
    mean = trajectories.mean_trajectories(tracks, schema, track, n_steps=10, formants=["F1", "F2"])
    assert {"vowel", "step", "F1", "F2", "n"}.issubset(mean.columns)
    assert mean["step"].max() == 9

    def movement(vowel):
        sub = mean[mean.vowel == vowel].sort_values("step")
        return np.hypot(sub["F1"].iloc[-1] - sub["F1"].iloc[0],
                        sub["F2"].iloc[-1] - sub["F2"].iloc[0])

    # PRICE (AY) is a diphthong; LOT (AA) is ~monophthong.
    assert movement("AY") > movement("AA")
