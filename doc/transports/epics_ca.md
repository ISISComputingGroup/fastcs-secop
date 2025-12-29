# EPICS Channel Access

EPICS CA transport requires `fastcs[epicsca]` to be installed.

EPICS CA has a maximum length of 40 on parameter descriptions. Set {py:obj}`fastcs_secop.SecopQuirks.max_description_length` to 40 to truncate descriptions.

## Supported SECoP data types

EPICS CA transport supports the following {external+secop:doc}`SECoP data types <specification/datainfo>`:
- double
- scaled
- int
- bool
- enum
- string
- blob
- array of double/int/bool/{ref}`enum* <limitations_enum>`/string
- command (if arguments and return values are empty or one of the above types)

Other data types can only be read in 'raw' mode.

## Example CA IOC

:::python
```{literalinclude} ../../examples/epics_ca.py
```
:::
