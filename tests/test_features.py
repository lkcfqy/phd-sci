import numpy as np
import pandas as pd

from pmsm_sci.features import add_physics_features


def test_physics_feature_values() -> None:
    frame = pd.DataFrame(
        {
            "i_d": [3.0],
            "i_q": [4.0],
            "u_d": [5.0],
            "u_q": [12.0],
            "torque": [-2.0],
            "motor_speed": [100.0],
        }
    )
    result = add_physics_features(frame)
    assert np.isclose(result.loc[0, "current_magnitude"], 5.0)
    assert np.isclose(result.loc[0, "voltage_magnitude"], 13.0)
    assert np.isclose(result.loc[0, "copper_loss_proxy"], 25.0)
    assert np.isclose(result.loc[0, "electrical_power_proxy"], 63.0)
    assert np.isclose(result.loc[0, "mechanical_power_proxy"], 200.0)
