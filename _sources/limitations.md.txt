# Limitations

There are some elements of the {external+secop:doc}`SECoP specification <specification/index>` that
{py:obj}`fastcs_secop` does not currently support. These are detailed below.

{#limitations_dtype}
## Data-type limitations

{#limitations_float_format}
### Float formatting

For double and scaled type parameters, the format string (`fmtstr`) is interpreted only if it is in the `f` format. `g`
and `e` formats are ignored.

Rationale: FastCS provides a `precision` argument to transports, which represents a number of decimal places. 
Other formats are not currently representable in FastCS.

{#limitations_enum}
### Enums within arrays/structs/tuples

An enum-type element *within* an array/struct/tuple is treated as its corresponding integer value and loses name-based
functionality.

Rationale: FastCS does not provide a way to describe an enum nested within a {py:obj}`~fastcs.datatypes.table.Table`
or {py:obj}`~fastcs.datatypes.waveform.Waveform`. Most transports also cannot describe this.

{#limitations_nested_complex}
### Nested arrays/structs/tuples

Arrays/structs/tuples nested inside another array/struct/tuple are not supported. Arrays, structs and tuples can only
be made from 'simple' data types (double, int, bool, enum, string).

Nested arrays create the possibility of ragged arrays, which cannot be expressed using standard {py:obj}`numpy`
datatypes and are not representable using FastCS's current data types.

In principle, the following types could be supported in future (but are not supported currently):
- Arrays of structs or tuples, using the {py:obj}`~fastcs.datatypes.table.Table` type (for transports that support
the {py:obj}`~fastcs.datatypes.table.Table` FastCS type).
- Nested combinations of structs and tuples, by flattening (for transports that support
the {py:obj}`~fastcs.datatypes.table.Table` FastCS type). 

Workaround: Use {py:obj}`fastcs_secop.SecopQuirks.skip_accessibles` to skip the accessible, or use
{py:obj}`fastcs_secop.SecopQuirks.raw_accessibles` to read/write to the accessible in
'raw' mode, which treats the SECoP JSON value as a string.

You can also use {py:obj}`fastcs_secop.SecopQuirks.raw_tuple` / {py:obj}`~fastcs_secop.SecopQuirks.raw_struct`
/ {py:obj}`~fastcs_secop.SecopQuirks.raw_array` to unconditionally read any tuple/struct/array channel in raw mode.

{#limitations_async}
## Asynchronous updates

Asynchronous updates are not supported by {py:obj}`fastcs_secop`. They are turned off using a 
{external+secop:doc}`deactivate message <specification/messages/activation>` at connection time.

Rationale: FastCS does not currently provide infrastructure to handle asynchronous messages.

{#limitations_qualifiers}
## Timestamp and error qualifiers

These are ignored; FastCS currently exposes no mechanism to set these. If such a mechanism is later added to FastCS,
they may become supportable here.
