# EPICS PV Access

EPICS PVA transport requires `fastcs[epicspva]` to be installed.

## Supported SECoP data types

EPICS PVA transport supports the following {external+secop:doc}`SECoP data types <specification/datainfo>` (using the corresponding {external+epics:doc}`PVA normative types <pv-access/Normative-Types-Specification>`):
- double (`NTScalar[double]`)
- scaled (`NTScalar[double]`)
- int (`NTScalar[int]`)
- bool (`NTScalar[boolean]`)
- enum (`NTEnum`)
- string (`NTScalar[string]`)
- blob (`NTNDArray[ubyte]`)
- array of double/int/bool/{ref}`enum* <limitations_enum>` (`NTNDArray`)
- tuple of double/int/bool/{ref}`enum* <limitations_enum>`/string elements (`NTTable` with one row)
- struct of double/int/bool/{ref}`enum* <limitations_enum>`/string elements (`NTTable` with one row)
- matrix (`NTNDArray`)
- command (if arguments and return values are empty or one of the above types)

Other data types can only be read or written in 'raw' mode.

## PVI

{py:obj}`fastcs` exports PVI PVs with the PVA transport.

SECoP modules can be found under the top-level PVI structure, while SECoP accessibles can be found under
`module_name:PVI`. This means that the IOC is self-describing to downstream clients.

{#example_pva_ioc}
## Example PVA IOC

:::python
```{literalinclude} ../../examples/epics_pva.py
```
:::
