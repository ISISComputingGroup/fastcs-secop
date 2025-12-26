# Limitations

There are some elements of the {external+secop:doc}`SECoP specification <specification/index>` that
{py:obj}`fastcs_secop` does not currently support. These are detailed below.

## Data-type limitations

### Enums within arrays/structs/tuples

An enum-type element *within* an array/struct/tuple is treated as its corresponding integer value and loses name-based
functionality.

Rationale: FastCS does not provide a way to describe an enum nested within a {py:obj}`~fastcs.datatypes.table.Table`
or {py:obj}`~fastcs.datatypes.waveform.Waveform`.

### Nested arrays/structs/tuples

Arrays/structs/tuples nested inside another array/struct/tuple are not supported. Arrays, structs and tuples can only
be made from 'simple' data types (double, int, bool, enum, string).

Rationale: most FastCS transports cannot support these nested datatypes easily. Nested arrays create the possibility
of ragged arrays which cannot be expressed using standard {py:obj}`numpy` datatypes.

Workaround: Use {py:obj}`fastcs_secop.SecopQuirks` to either skip the accessible, or read it in
'raw' mode which treats the SECoP JSON response as a string to be interpreted downstream, rather than deserialising it.

## Transport-specific limitations

FastCS supports multiple transport types (e.g. EPICS CA, EPICS PVA, Tango, REST, ...). However, not all datatypes are
supported using all transports. Notably, EPICS CA lacks support for the {py:obj}`~fastcs.datatypes.table.Table` type,
which is used to implement structs and tuples.

Workaround: Use {py:obj}`fastcs_secop.SecopQuirks` to either skip the accessible, or read it in
'raw' mode, which treats the SECoP JSON response as a string to be interpreted downstream, rather than deserialising it.
A {py:obj}`~collections.defaultdict` can be used to specify reading *all* arrays, structs or tuples in raw mode.

## Asynchronous updates

Asynchronous updates are not supported by {py:obj}`fastcs_secop`. They are turned off using a 
{external+secop:doc}`deactivate message <specification/messages/activation>` at connection time.

Rationale: FastCS does not currently provide infrastructure to handle asynchronous messages.
