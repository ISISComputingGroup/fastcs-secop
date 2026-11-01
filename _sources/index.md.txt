# `fastcs-secop` documentation

The {py:obj}`fastcs_secop` library implements support for the {external+secop:doc}`SECoP protocol <specification/index>`
using {external+fastcs:doc}`FastCS <index>`.

```{mermaid}
erDiagram
    "EPICS Clients" }o--o| "fastcs + fastcs-secop" : "EPICS CA"
    "EPICS Clients" }o--o| "fastcs + fastcs-secop" : "EPICS PVA"
    "Tango Clients" }o--o| "fastcs + fastcs-secop" : "Tango"
    "fastcs + fastcs-secop" ||--|| "SEC Node" : SECoP
```

```{toctree}
:titlesonly:
:caption: Transports
:glob:

transports/*
```

```{toctree}
:titlesonly:
:caption: Reference

contributing
limitations
_api
```
