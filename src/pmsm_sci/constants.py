"""Dataset schema constants."""

BASE_FEATURES = [
    "ambient",
    "coolant",
    "u_d",
    "u_q",
    "i_d",
    "i_q",
    "motor_speed",
    "torque",
]

TARGETS = ["pm", "stator_yoke", "stator_tooth", "stator_winding"]
GROUP_COLUMN = "profile_id"
REQUIRED_COLUMNS = BASE_FEATURES + TARGETS + [GROUP_COLUMN]

PHYSICS_FEATURES = [
    "current_magnitude",
    "voltage_magnitude",
    "copper_loss_proxy",
    "electrical_power_proxy",
    "mechanical_power_proxy",
]
