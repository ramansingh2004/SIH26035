"""Candidate identifiers, not implemented evaluators or applicability decisions."""

SECTIONS = (
    "WEIGHING_PERFORMANCE",
    "TEMPERATURE_ZERO",
    "ECCENTRICITY",
    "DISCRIMINATION_SENSITIVITY",
    "REPEATABILITY",
    "TIME_DEPENDENCE",
    "STABILITY_EQUILIBRIUM",
    "TILTING",
    "TARE",
    "WARM_UP",
    "VOLTAGE_VARIATION",
    "ELECTRICAL_DISTURBANCES",
    "DAMP_HEAT",
    "SPAN_STABILITY",
    "ENDURANCE",
    "CONSTRUCTION_EXAMINATION",
    "CHECKLIST",
)
FAMILIES = {
    4: ("DISCRIMINATION", "SENSITIVITY"),
    6: ("ZERO_RETURN", "CREEP"),
    12: tuple(
        "DISTURBANCE_" + name
        for name in (
            "VOLTAGE_DIP",
            "BURST",
            "SURGE",
            "ESD",
            "RADIATED_RF",
            "CONDUCTED_RF",
            "VEHICLE_SUPPLY",
        )
    ),
}
CHECKLIST_DOMAINS = {
    "GENERAL": (
        "MARKINGS",
        "SEALING",
        "DOCUMENTATION",
        "INDICATION",
        "PRINTING",
        "ZERO_SETTING",
        "TARE",
        "RANGES",
        "EXTENDED_INDICATION",
        "INTERFACES",
    ),
    "DIRECT_SALES": (
        "CUSTOMER_VISIBILITY",
        "PRICE_DISPLAY",
        "TARE_RESTRICTIONS",
        "AUTOMATIC_FUNCTIONS",
        "LABELING",
        "TRANSACTIONS",
    ),
    "ELECTRONIC": (
        "FAULT_HANDLING",
        "POWER_UP",
        "DISPLAY_TEST",
        "INTERFACES",
        "PERIPHERALS",
        "BATTERY",
        "FUNCTIONAL_INTEGRITY",
    ),
    "SOFTWARE_CONTROLLED": (
        "EMBEDDED_SOFTWARE",
        "LOADABLE_SOFTWARE",
        "SOFTWARE_IDENTIFICATION",
        "DATA_STORAGE",
    ),
}
