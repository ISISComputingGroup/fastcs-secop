# EPICS PV Access

EPICS PVA transport requires `fastcs[epicspva]` to be installed.

## Supported SECoP data types

EPICS PVA transport supports the following {external+secop:doc}`SECoP data types <specification/datainfo>`:
- double
- scaled
- int
- bool
- enum
- string
- blob
- array of double/int/bool/{ref}`enum* <limitations_enum>`/string
- tuple of double/int/bool/{ref}`enum* <limitations_enum>`/string elements
- struct of double/int/bool/{ref}`enum* <limitations_enum>`/string elements
- matrix

Other data types can only be read in 'raw' mode.

## PVI

{py:obj}`fastcs` exports PVI PVs with the PVA transport.

SECoP modules can be found under the top-level PVI structure, while SECoP accessibles can be found under
`module_name:PVI`. This means that the IOC is self-describing to downstream clients.

## Example PVA IOC

:::python
```{literalinclude} ../../examples/epics_pva.py
```
:::
