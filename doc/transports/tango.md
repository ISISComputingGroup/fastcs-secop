# Tango

Tango transport requires `fastcs[tango]` to be installed.

## Supported SECoP data types

Tango transport supports the following {external+secop:doc}`SECoP data types <specification/datainfo>`:
- double
- scaled
- int
- bool
- enum
- string
- blob
- array of double/int/bool/{ref}`enum* <limitations_enum>`/string
- matrix (if the matrix has dimensionality <= 2)
- command (if arguments and return values are empty or one of the above types)

Other data types can only be read in 'raw' mode.
