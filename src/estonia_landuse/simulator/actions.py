"""Land-use types and action representation.

V2: Actions are continuous — the prescriptor outputs target land-use fractions
per cell. The "action" is the transition from current to target distribution.

Land-use types match what CORINE gives us, grouped into manageable categories.
"""

# Land-use group indices (order matters — matches prescriptor output)
LAND_USE_GROUPS = ["forest", "wetland", "agriculture", "grassland", "urban"]
N_LAND_USE_GROUPS = len(LAND_USE_GROUPS)

# Groups that can be changed by the prescriptor
CHANGEABLE_GROUPS = ["forest", "wetland", "agriculture", "grassland"]

# Groups that are fixed (prescriptor cannot modify)
FIXED_GROUPS = ["urban", "water"]
